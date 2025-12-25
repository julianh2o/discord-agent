client<llm> Ollama {
  provider ollama
  options {
    base_url env.OLLAMA_URL
    model env.OLLAMA_MODEL
  }
}
