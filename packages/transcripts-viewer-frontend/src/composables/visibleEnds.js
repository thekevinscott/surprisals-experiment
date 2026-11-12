export function visibleEnds(items, expanded) {
  return expanded || items.length <= 2 ? items : [items[0], items.at(-1)]
}
