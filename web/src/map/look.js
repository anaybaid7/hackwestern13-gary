// Which map to draw: the 3D one where this browser can, the flat one
// otherwise, and whichever the person last chose (kept in this browser only).
const LOOK_KEY = 'gary.map.look'
let webgl = null // asked once: making a drawing surface is not free

/** Can this browser draw the 3D map (WebGL)? */
export function can3d() {
  if (webgl === null) {
    try {
      // a test page (jsdom) has no WebGL, and says so without drawing anything
      if (typeof window === 'undefined' || typeof WebGLRenderingContext === 'undefined') webgl = false
      else {
        const canvas = document.createElement('canvas')
        webgl = Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
      }
    } catch {
      webgl = false
    }
  }
  return webgl
}

/** '3d' (the default) or 'flat'. */
export function savedLook() {
  try {
    return window.localStorage.getItem(LOOK_KEY) === 'flat' ? 'flat' : '3d'
  } catch {
    return '3d'
  }
}

export function saveLook(look) {
  try {
    window.localStorage.setItem(LOOK_KEY, look)
  } catch {
    // private window, storage off: the choice lasts until the page closes
  }
}

/** For tests: forget what was found about WebGL. */
export function forgetWebgl(value = null) {
  webgl = value
}
