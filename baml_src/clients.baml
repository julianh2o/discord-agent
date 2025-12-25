client<llm> Ollama {
  provider openai
  options {
    base_url env.OLLAMA_URL
    api_key "ollama" // Ollama doesn't require a real API key
    model env.OLLAMA_MODEL
  }
}
