// Pixel art from text. A drawing is a list of equal-length strings; each
// character is one pixel and names a colour in the palette ('.' is empty).
// Runs of one colour on a row become one <rect>, so a 32 x 32 goat is a few
// hundred rectangles, not a thousand.

export const INK = '#14202B'
export const CREAM = '#FFF4DA'
export const LCD = '#C8F56B'
export const CORAL = '#FF5A47'
export const ORANGE = '#FF9F43'

/** -> [{x, y, w, fill}] for every run of one colour. */
export function runs(rows, palette) {
  const out = []
  rows.forEach((row, y) => {
    let x = 0
    while (x < row.length) {
      const ch = row[x]
      let end = x + 1
      while (end < row.length && row[end] === ch) end += 1
      if (palette[ch]) out.push({ x, y, w: end - x, fill: palette[ch] })
      x = end
    }
  })
  return out
}

/** The drawing as an SVG document, for an <img> (so it keeps a real alt text). */
export function svgDataUri(rows, palette) {
  const size = rows[0].length
  const rects = runs(rows, palette)
    .map((r) => `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="1" fill="${r.fill}"/>`)
    .join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${rows.length}" shape-rendering="crispEdges">${rects}</svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

/** Writes `text` into `rows` at (row, col), leaving '.'s in `text` as they were. */
export function patch(rows, row, col, text) {
  const line = rows[row].split('')
  for (let i = 0; i < text.length; i += 1) if (text[i] !== ' ') line[col + i] = text[i]
  rows[row] = line.join('')
}
