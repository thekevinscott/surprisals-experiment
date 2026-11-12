export function uContext(messages, context) {
  if (!context) return []
  return [context.system == null ? null : messages[context.system], ...messages.slice(context.start, context.end + 1).filter(message => message.inContext && message.role !== 'system')].filter(Boolean)
}
