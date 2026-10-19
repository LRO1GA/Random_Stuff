I need a communications summary of my Teams and Outlook activity from {{START_DATE}} to {{END_DATE}} ({{RANGE_LABEL}}).

Please answer using exactly this Markdown structure, with no extra top-level headings and no text before or after it:

## Global Summary
A short paragraph summarizing the overall communications and work discussed during this period.

## Detailed Summary
Break this down by day. For each day in the range that had activity, add a subsection like this:

### <Day of week, Month Day>
- Topics discussed: ...
- Decisions made: ...
- People involved: ...

## Tasks Mentioned
A flat bullet list of tasks that were mentioned as being worked on, assigned, or followed up on during this period.

## Metrics
Format the **Metrics** section using exactly the following structure:

- People/groups messaged: <N>
- Messages sent by me: <N>
- Most messaged person: <Name> (<N> messages)
- Day with most volume: <Date> (<N> interactions)

Include only the metric values in these four bullets. Do not use qualifiers such as "at least," "approximately," "about," or "cannot be determined" within the bullets. Use the best estimates supported by the retrieved Teams and Outlook activity. After the four bullets, add this exact note:

*Note: All metrics are estimates based on the Teams and Outlook activity available for the specified period.*

Output File Requirements
Create the complete response as a downloadable Markdown file (.md) using valid Markdown formatting.

- Include the full requested summary in the file, not merely a link or abbreviated version.
- Preserve the exact heading structure, subsection order, bullet formatting, metrics format, and final estimates note specified above.
- Name the file: communications_summary_<START-DATE>_to_<END-DATE>.md.
- Return a clickable download link to the completed Markdown file.
- Do not create a Word, PDF, HTML, or plain-text file.
