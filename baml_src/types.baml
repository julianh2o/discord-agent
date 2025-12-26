// Message types for conversation history
class Message {
  role "user" | "assistant" | "tool" | "error"
  content string
}

// Tool definitions
class FetchUrlTool {
  url string @description("The URL to fetch content from")
  reason string @description("Brief explanation of why this URL is relevant to the user's question")
}

class GetOllamaModelsTool {
  reason string @description("Brief explanation of why you need to know available models")
}

class GetStoredContentTool {
  sha_key string @description("The 8-character SHA key from a previous tool result (e.g., 'a1b2c3d4')")
  reason string @description("Brief explanation of why you need this stored content")
}

class TavilySearchTool {
  query string @description("The search query to send to Tavily for web research")
  reason string @description("Brief explanation of why this search is relevant to the user's question")
}

// Action tools (require user approval)
class ReadFileTool {
  file_path string @description("The absolute or relative path to the file to read")
  reason string @description("Brief explanation of why you need to read this file")
}

class WriteFileTool {
  file_path string @description("The absolute or relative path to the file to write")
  content string @description("The content to write to the file")
  reason string @description("Brief explanation of why you need to write this file")
}

class BashTool {
  command string @description("The bash command to execute")
  reason string @description("Brief explanation of why you need to run this command")
}

// Agent orchestration actions - the agent chooses one of these
class GatherInformation {
  reasoning string @description("Brief explanation of what information is needed")
  tool_calls (FetchUrlTool | GetOllamaModelsTool | GetStoredContentTool | TavilySearchTool)[] @description("List of tools to execute to gather information")
}

class AskUser {
  reasoning string @description("Brief explanation of why clarification is needed")
  question string @description("The clarifying question to ask the user")
  options string[] @description("2-4 options for the user to choose from")
}

class PerformAction {
  reasoning string @description("Brief explanation of what action needs to be performed")
  tool_calls (ReadFileTool | WriteFileTool | BashTool)[] @description("List of tools to execute (requires user approval)")
}

class FinalAnswer {
  reasoning string @description("Brief explanation of the conclusion")
  response string @description("The final response to send to the user")
}
