client<llm> OrchestratorModel {
  provider openai
  options {
    base_url env.OLLAMA_URL
    model "llama3.1:8b"
    num_ctx 32768
  }
}

// Fast, small model for summarization tasks
client<llm> SummarizationModel {
  provider openai
  options {
    base_url env.OLLAMA_URL
    model "qwen3:4b"
  }
}
