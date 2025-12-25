// Message types for conversation history
class Message {
  role "user" | "assistant" | "tool"
  content string
}

// Tool definitions
class FetchUrlTool {
  url string @description("The URL to fetch content from")
  reason string @description("Brief explanation of why this URL is relevant to the user's question")
}

// Agent action types - the agent chooses one of these
class ContinueResearch {
  reasoning string @description("Brief explanation of why more research is needed")
  tool_calls FetchUrlTool[] @description("List of URLs to fetch for more information")
}

class FinalResponse {
  response string @description("The final response to send to the user")
}

class AskUser {
  question string @description("The clarifying question to ask the user")
  options string[] @description("2-4 options for the user to choose from")
}
