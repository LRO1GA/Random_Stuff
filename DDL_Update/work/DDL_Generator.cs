// DDL Generator
// Author: Rafael Arroyo Tamayo.
// Developed in the Microsoft Visual Studio environment.
// NuGet packages used:
// - EPPlus, by EPPlus software.
// - CsvHelper, by Josh Close.
// - Aspose.Cells, by Aspose.

using CsvHelper;
using OfficeOpenXml;
using System.Globalization;
using CsvHelper.Configuration;
using Microsoft.VisualBasic.FileIO;
using OfficeOpenXml.Style;

class Program
{
    static void Main(string[] args)
    {
        // Establece el contexto de licencia
        ExcelPackage.License.SetNonCommercialOrganization("DDL Generator Internal Tool");

        bool dryRun = args.Length > 0 && string.Equals(args[0], "--dry-run", StringComparison.OrdinalIgnoreCase);

        string customer;
        string input_path;
        string output_file;

        if (dryRun)
        {
            // --dry-run <input_folder> <customer> [output_folder]
            if (args.Length < 3)
            {
                Console.WriteLine("Usage (dry run): --dry-run <input_folder> <customer> [output_folder]");
                System.Environment.Exit(1);
                return;
            }

            input_path = args[1];
            customer = args[2];
            string output_dir = args.Length > 3 ? args[3] : input_path;
            Directory.CreateDirectory(output_dir);
            output_file = Path.Combine(output_dir, customer + "_DryRun.xlsx");

            Console.WriteLine(">>> Dry run mode: reading inputs directly from " + input_path);
        }
        else
        {
            // Almacena los valores de los parametros
            customer = args[0];
            string build_id = args[1];

            if (string.IsNullOrEmpty(build_id) ||
                string.IsNullOrEmpty(customer))
            {
                Console.WriteLine("The parameters are not set correctly.");
                System.Environment.Exit(1);
            }

            // Find the Gen directory
            FindGenDirectory();

            string current_path = Directory.GetCurrentDirectory();

            input_path = current_path + "\\Gen\\" + build_id + "\\src_out\\DDL";
            string output_path = current_path + "\\Gen\\" + build_id + "\\out";
            string filename = customer + "_" + build_id + ".xlsx";
            output_file = output_path + "\\" + filename;
        }

        string DTC_Vs_TCManeuver = FindInputFile(input_path, "DTC_Vs_TCManeuver_Project");
        string STM_SystemReleaseTable = FindInputFile(input_path, "STM_SystemReleaseTableExpand_Project");
        string DiagnosisDataList = FindInputFile(input_path, "DiagnosisDataList_Project");

        string[] ddl_excluded = new string[6] { "FW_NAME", "IUMPR_DENGROUP", "DTC_NAME", "SFB_COUNT", "SFB_TIME", "" };
        string[] dtc_included = new string[5] { "DTC_NAME", "DTC_VALUE", "TEST_COMPLETE_MANEUVER","TEST_COMPLETE_MANEUVER_DESC", "FW_NAME"};

        List<int> indices_ddl_excluded = new List<int>();
        List<int> indices_dtc_included = new List<int>();

        // Comprueba que los valores no esten vacios
        if (string.IsNullOrEmpty(output_file) ||
            string.IsNullOrEmpty(DTC_Vs_TCManeuver) ||
            string.IsNullOrEmpty(STM_SystemReleaseTable) ||
            string.IsNullOrEmpty(DiagnosisDataList))
        {
            Console.WriteLine("Parameters are not set correctly.");
            System.Environment.Exit(1);
        }
        else
        {
            Console.WriteLine("File paths set correctly.");
        }

        // Crear un nuevo archivo de Excel
        try
        {
            if (!File.Exists(DiagnosisDataList) || !File.Exists(STM_SystemReleaseTable))
            {
                Console.WriteLine("Error: Required input CSV files were not found in: " + input_path);
                System.Environment.Exit(1);
                return;
            }

            if (File.Exists(output_file))
            {
                Console.WriteLine("Error: Output file already exists with the same name.");
                System.Environment.Exit(1);
            }

            // Projects export the CSVs with or without a leading "sep=;" directive line, which shifts where the real header row is
            bool ddlHasSepLine = HasSepLine(DiagnosisDataList);
            bool srtHasSepLine = HasSepLine(STM_SystemReleaseTable);

            // Establecer los indices de las columnas para filtrar en DDL y DTC
            GetColumnIndex(DiagnosisDataList, ddl_excluded, indices_ddl_excluded, ddlHasSepLine);
            GetColumnIndex(DiagnosisDataList, dtc_included, indices_dtc_included, ddlHasSepLine);
            int dtc_columns_count = indices_dtc_included.Count;

            // Crear un nuevo archivo de Excel
            FileInfo file = new FileInfo(output_file);
            using (ExcelPackage package = new ExcelPackage(file))
            {
                // Crear las hojas
                ExcelWorksheet coverSheet = package.Workbook.Worksheets.Add("Cover");
                ExcelWorksheet ddlSheet = package.Workbook.Worksheets.Add("DDL");
                ExcelWorksheet srtSheet = package.Workbook.Worksheets.Add("SRT");
                ExcelWorksheet dtcSheet = package.Workbook.Worksheets.Add("DTC");

                // Llenar la hoja "Cover"
                FillCover(package, customer);

                // Llenar la hoja "DDL"
                FillDDL(ddlSheet, DiagnosisDataList, indices_ddl_excluded, ddlHasSepLine);

                // Llenar la hoja "SRT"
                FillSRT(srtSheet, STM_SystemReleaseTable, srtHasSepLine);

                // Llenar la hoja "DTC"
                FillDTC(dtcSheet, DiagnosisDataList, indices_dtc_included, dtc_columns_count, ddlHasSepLine);

                // Guardar los cambios en el archivo
                package.Save();
            }

            Console.WriteLine("Output file created successfully: " + output_file);
        }
        // Manejo de errores
        catch (KeyNotFoundException ex)
        {
            Console.WriteLine("Error: Expected column not found in the input CSV: " + ex.Message);
        }
        catch (IOException ex)
        {
            Console.WriteLine("Error: Input/output exception occurred: " + ex.Message);
        }
        catch (UnauthorizedAccessException ex)
        {
            Console.WriteLine("Error: Unauthorized access exception occurred: " + ex.Message);
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error: An unexpected exception occurred: " + ex.Message);
        }
    }

    // Some project exports prefix the CSV with a "sep=;" directive line before the real header row
    static bool HasSepLine(string filePath)
    {
        using (var reader = new StreamReader(filePath))
        {
            string firstLine = reader.ReadLine();
            return firstLine != null && firstLine.Replace("\"", "").Trim().StartsWith("sep=", StringComparison.OrdinalIgnoreCase);
        }
    }

    // Tolerates duplicate-download suffixes like "DiagnosisDataList_Project (1).csv"
    static string FindInputFile(string folder, string baseName)
    {
        string exact = Path.Combine(folder, baseName + ".csv");
        if (File.Exists(exact) || !Directory.Exists(folder))
        {
            return exact;
        }

        string[] matches = Directory.GetFiles(folder, baseName + "*.csv");
        return matches.Length > 0 ? matches[0] : exact;
    }

    static void FillCover(ExcelPackage package, string customer)
    {
        string timeStamp = GetTimestamp(DateTime.Now);

        // Acceder a la hoja "Cover"
        ExcelWorksheet coverSheet = package.Workbook.Worksheets["Cover"];

        // Establecer el ancho de las columnas A, B y C
        coverSheet.Column(1).Width = 45;
        coverSheet.Column(2).Width = 45;
        coverSheet.Column(3).Width = 20;

        // Fusionar celdas desde A1 hasta B2
        coverSheet.Cells["A1:B2"].Merge = true;

        // Escribir "Diagnostic Data List" en A1
        var cellA1 = coverSheet.Cells["A1"];
        cellA1.Value = "Diagnostic Data List";
        cellA1.Style.Font.Size = 16;
        cellA1.Style.Font.Bold = true;
        cellA1.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA1.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));
        cellA1.Style.Font.Color.SetColor(System.Drawing.ColorTranslator.FromHtml("#F0F0F0"));
        cellA1.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellA1.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        // Fusionar celdas A3 y A4, y escribir el valor de "customer" en A3
        coverSheet.Cells["A3:A4"].Merge = true;
        var cellA3 = coverSheet.Cells["A3"];
        cellA3.Value = customer;
        cellA3.Style.Font.Size = 16;
        cellA3.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA3.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#f0f8ff"));
        cellA3.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellA3.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        // Fusionar celdas y establecer el color
        coverSheet.Cells["A7:C7"].Merge = true;
        coverSheet.Cells["A15:C15"].Merge = true;
        var cellA7 = coverSheet.Cells["A7"];
        var cellA15 = coverSheet.Cells["A15"];
        cellA7.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA7.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));
        cellA15.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA15.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));

        // Escribir el valor de "baseline" en A12
        var cellA11 = coverSheet.Cells["A11"];
       // cellA11.Value = "Baseline";
        cellA11.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA11.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));
        cellA11.Style.Font.Bold = true;
        cellA11.Style.Font.Color.SetColor(System.Drawing.ColorTranslator.FromHtml("#F0F0F0"));
        cellA11.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellA11.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        var cellA12 = coverSheet.Cells["A12"];
       // cellA12.Value = baseline;
        cellA12.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellA12.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#f0f8ff"));
        cellA12.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellA12.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        // Escribir "Date of delivery" en C11 y el valor de "timeStamp" en C12
        var cellC11 = coverSheet.Cells["C11"];
        var cellC12 = coverSheet.Cells["C12"];
        cellC11.Value = "Date of delivery";
        cellC11.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellC11.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));
        cellC11.Style.Font.Bold = true;
        cellC11.Style.Font.Color.SetColor(System.Drawing.ColorTranslator.FromHtml("#F0F0F0"));
        cellC11.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellC11.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        cellC12.Value = timeStamp;
        cellC12.Style.Fill.PatternType = ExcelFillStyle.Solid;
        cellC12.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#f0f8ff"));
        cellC12.Style.HorizontalAlignment = ExcelHorizontalAlignment.Center;
        cellC12.Style.VerticalAlignment = ExcelVerticalAlignment.Center;

        Console.WriteLine("Cover sheet created.");
    }
    static void FillDDL(ExcelWorksheet ddlSheet, string diagnosisDataList, List<int> indices_ddl_excluded, bool hasSepLine)
    {
        int rowIndex = 1;
        int linesToSkip = hasSepLine ? 1 : 0; // Skip only the "sep=;" line, if present, so the codes header row is kept

        using (var reader = new StreamReader(diagnosisDataList))
        {
            int skippedLines = 0;

            while (!reader.EndOfStream)
            {
                string line = reader.ReadLine();
                if (line != null)
                {
                    if (skippedLines < linesToSkip)
                    {
                        skippedLines++;
                        continue;
                    }

                    string[] values = line.Split(';'); // Separar los valores por coma (CSV)

                    List<string> filteredValues = new List<string>();
                    for (int colIndex = 0; colIndex < values.Length; colIndex++)
                    {
                        if (!indices_ddl_excluded.Contains(colIndex))
                        {
                            string trimmedValue = values[colIndex].Trim(); // Eliminar espacios en blanco alrededor del valor
                            if (trimmedValue.StartsWith("\"") && trimmedValue.EndsWith("\"") && trimmedValue.Length >= 2)
                            {
                                // Si el valor está entre comillas dobles, quitar las comillas y agregar a los valores filtrados
                                filteredValues.Add(trimmedValue.Substring(1, trimmedValue.Length - 2));
                            }
                            else
                            {
                                // Si el valor no está entre comillas dobles, agregar tal cual a los valores filtrados
                                filteredValues.Add(trimmedValue);
                            }
                        }
                    }

                    // Escribir los datos filtrados en la hoja de Excel
                    for (int colIndex = 0; colIndex < filteredValues.Count; colIndex++)
                    {
                        ddlSheet.Cells[rowIndex, colIndex + 1].Value = filteredValues[colIndex];
                    }

                    rowIndex++;
                }
            }
            // Establecer el ancho de las columnas y otros estilos
            SetSheetStyle(ddlSheet);
        }
        Console.WriteLine("DDL sheet created.");
    }
    // End FillDLL

    static void FillSRT(ExcelWorksheet srtSheet, string srtDataList, bool hasSepLine)
    {
        int rowIndex = 1;
        int linesToSkip = hasSepLine ? 2 : 1; // Skip "sep=;" (if present) + codes header, keeping the description row as the sheet header

        using (var reader = new StreamReader(srtDataList))
        {
            int skippedLines = 0;

            while (!reader.EndOfStream)
            {
                string line = reader.ReadLine();
                if (line != null)
                {
                    if (skippedLines < linesToSkip)
                    {
                        skippedLines++;
                        continue;
                    }

                    string[] values = line.Split(';'); // Separar los valores por coma (CSV)

                    List<string> filteredValues = new List<string>();
                    foreach (string value in values)
                    {
                        string trimmedValue = value.Trim(); // Eliminar espacios en blanco alrededor del valor
                        if (trimmedValue.StartsWith("\"") && trimmedValue.EndsWith("\"") && trimmedValue.Length >= 2)
                        {
                            // Si el valor está entre comillas dobles y la longitud es suficiente, quitar las comillas y agregar a los valores filtrados
                            filteredValues.Add(trimmedValue.Substring(1, trimmedValue.Length - 2));
                        }
                        else
                        {
                            // Si el valor no está entre comillas dobles o la longitud es insuficiente, agregar tal cual a los valores filtrados
                            filteredValues.Add(trimmedValue);
                        }
                    }

                    // Escribir los datos filtrados en la hoja de Excel
                    for (int colIndex = 0; colIndex < filteredValues.Count; colIndex++)
                    {
                        srtSheet.Cells[rowIndex, colIndex + 1].Value = filteredValues[colIndex];
                    }

                    rowIndex++;
                }
            }
            // Establecer el ancho de las columnas y otros estilos
            SetSheetStyle(srtSheet);
        }
        Console.WriteLine("SRT sheet created.");
    }
    // End SRT

    static void FillDTC(ExcelWorksheet ddlSheet, string diagnosisDataList, List<int> indices_dtc_included, int dtc_columns_count, bool hasSepLine)
    {
        int rowIndex = 1;
        int linesToSkip = hasSepLine ? 1 : 0; // Skip only the "sep=;" line, if present, so the codes header row is kept

        var csvConfig = new CsvConfiguration(CultureInfo.InvariantCulture)
        {
            BadDataFound = null, // Ignorar datos incorrectos
            HasHeaderRecord = false // No esperar una fila de encabezado
        };

        using (var reader = new StreamReader(diagnosisDataList))
        using (var csv = new CsvReader(reader, csvConfig))
        {
            int skippedLines = 0;

            while (!reader.EndOfStream)
            {
                string line = reader.ReadLine();
                if (line != null)
                {
                    if (skippedLines < linesToSkip)
                    {
                        skippedLines++;
                        continue;
                    }

                    string[] values = line.Split(';'); // Separar los valores por coma (CSV)

                    List<string> filteredValues = new List<string>();

                    foreach (int i in indices_dtc_included)
                    {
                        string trimmedValue = values[i].Trim();
                        if (trimmedValue.StartsWith("\"") && trimmedValue.EndsWith("\"") && trimmedValue.Length >= 2)
                        {
                            filteredValues.Add(trimmedValue.Substring(1, trimmedValue.Length - 2));
                        }
                        else
                        {
                            filteredValues.Add(trimmedValue);
                        }
                    }

                    // Escribir los datos filtrados en la hoja de Excel
                    for (int colIndex = 0; colIndex < dtc_columns_count; colIndex++)
                    {
                        ddlSheet.Cells[rowIndex, colIndex + 1].Value = filteredValues[colIndex];
                    }

                    rowIndex++;
                }
            }
            // End while
            SetSheetStyle(ddlSheet);
        }
        Console.WriteLine("DTC sheet created.");
    }
    // End FillDTC


    static void SetSheetStyle(ExcelWorksheet worksheet, int width = 25)
    {
        for (int col = 1; col <= worksheet.Dimension.End.Column; col++)
        {
            worksheet.Column(col).Width = width;
        }
        // Aplicar estilos a las celdas
        for (int col = 1; col <= worksheet.Dimension.End.Column; col++)
        {
            var cell = worksheet.Cells[1, col];
            var range = worksheet.Cells[2, col, worksheet.Dimension.End.Row, col];

            // Aplicar estilos a la primera fila
            cell.Style.Font.Bold = true;
            cell.Style.Fill.PatternType = ExcelFillStyle.Solid;
            cell.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#19637e"));
            cell.Style.Font.Color.SetColor(System.Drawing.ColorTranslator.FromHtml("#F0F0F0"));

            // Aplicar estilos al resto de las celdas
            range.Style.Fill.PatternType = ExcelFillStyle.Solid;
            range.Style.Fill.BackgroundColor.SetColor(System.Drawing.ColorTranslator.FromHtml("#f0f8ff"));
            range.Style.Border.BorderAround(ExcelBorderStyle.Thin);
        }

        // Fijar la primera fila en la parte superior para que siempre sea visible
        worksheet.View.FreezePanes(2, 1);
    }
    static void GetColumnIndex(string archivoCSV, string[] nombresColumnas, List<int> array_indices, bool hasSepLine)
    {
        try
        {
            using (TextFieldParser parser = new TextFieldParser(archivoCSV))
            {
                parser.TextFieldType = FieldType.Delimited;
                parser.SetDelimiters(";");
                // Saltar la línea "sep=;", si existe, para no confundirla con la fila de códigos
                if (hasSepLine && !parser.EndOfData) parser.ReadFields();
                // Obtener la fila de códigos de columna (ej. FW_NAME, DTC_NAME...)
                string[] secondRow = parser.ReadFields();

                // Crear un diccionario para almacenar nombres de columna e índices
                Dictionary<string, int> indiceColumnas = new Dictionary<string, int>();
                for (int i = 0; i < secondRow.Length; i++)
                {
                    indiceColumnas[secondRow[i]] = i;
                }

                // Modificar el array original para almacenar los índices de las columnas buscadas
                array_indices.Clear();
                foreach (var nombre in nombresColumnas)
                {
                    if (indiceColumnas.ContainsKey(nombre))
                    {
                        array_indices.Add(indiceColumnas[nombre]);
                    }
                    else if (!string.IsNullOrEmpty(nombre))
                    {
                        // Columns like IUMPR_DENGROUP are project-specific (e.g. OBD-only) and may legitimately not exist
                        Console.WriteLine("Warning: Column '" + nombre + "' not found in CSV header, skipping.");
                    }
                }
            }
        }
        catch (FileNotFoundException)
        {
            throw;
        }
        catch (IOException)
        {
            throw;
        }
        catch (Exception)
        {
            throw;
        }
    } // End GetColumnIndex

    public static String GetTimestamp(DateTime value)
    {
        return value.ToString("dd/MM/yyyy HH:mm:ss");
    }

    static void FindGenDirectory()
    {
        int back = 200;

        // Go up in the directory level and search for the Gen folder
        while (back > 0)
        {
            if (Directory.Exists("Gen"))
            {
                Console.WriteLine(">>> Project directory set.");
                return;
            }
            Directory.SetCurrentDirectory(@"..\");
            back--;
        }
        // If the Gen folder does not exist (is not found within 200 iterations)
        Console.WriteLine(">>> Gen folder was not found, the project directory is not set.");
        Environment.Exit(1);
    }
}