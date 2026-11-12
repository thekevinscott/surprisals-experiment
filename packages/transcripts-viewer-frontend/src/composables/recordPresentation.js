// Only separate the content field from its metadata; preserve its text exactly.
export function recordPresentation(raw) {
  try {
    const record = JSON.parse(raw)
    if (!record || typeof record !== 'object' || Array.isArray(record)) return { text: raw }
    const nested = record.message && typeof record.message === 'object' && !Array.isArray(record.message)
    const { content, ...rest } = nested ? record.message : record
    const metadata = nested ? { ...record, message: rest } : rest
    return {
      text: content === undefined ? '' : typeof content === 'string' ? content : Array.isArray(content) ? content.map(block => block.type === 'thinking' ? block.thinking : block.type === 'text' ? block.text : block.type === 'toolCall' ? `${block.name}\n${JSON.stringify(block.arguments, null, 2)}` : JSON.stringify(block, null, 2)).join('\n\n') : JSON.stringify(content, null, 2),
      ...(typeof rest.reasoning === 'string' ? { reasoning: rest.reasoning } : {}),
      metadata,
    }
  } catch { return { text: raw } }
}
