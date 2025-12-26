function SummarizeText(text: string, target_length: int) -> string {
  client SummarizationModel
  prompt #"
    You are a text summarization assistant. Your job is to condense the following text to approximately {{ target_length }} characters while preserving the most important information.

    Guidelines:
    - Keep the most critical information (error messages, key points, etc.)
    - Remove verbose details, stack traces (keep only the most relevant lines), and redundant information
    - Maintain clarity and readability
    - If it's an error message, keep the error type and the most relevant part of the stack trace
    - Be concise but informative

    Original text ({{ text|length }} characters):
    {{ text }}

    Provide a summarized version that is approximately {{ target_length }} characters:
  "#
}
