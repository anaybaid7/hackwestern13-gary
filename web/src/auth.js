// Signing in with Auth0. The backend says whether a tenant is set up
// (/api/auth/config); if not, this is switched off and the page works as
// before. Gary keeps no name and no e-mail address: the backend turns the
// Auth0 id into a fingerprint, and that is all it stores.

const OFF = (reason) => ({ enabled: false, reason, signedIn: false, token: async () => '' })

/**
 * -> {enabled, reason?, signedIn, signIn(), signOut(), token()}.
 * `load` brings in Auth0's library only when a tenant is set up.
 */
export async function createAuth({
  api = '',
  fetchFn = (...args) => fetch(...args),
  load = () => import('@auth0/auth0-spa-js'),
  location = window.location,
  history = window.history,
  secure = window.isSecureContext,
} = {}) {
  let config
  try {
    const reply = await fetchFn(`${api}/api/auth/config`)
    if (!reply.ok) return OFF('no-config')
    config = await reply.json()
  } catch {
    return OFF('no-config')
  }
  if (!config.enabled || !config.client_id) return OFF('not-set-up')
  // Auth0's library needs the browser's crypto, which exists only on https and on localhost.
  if (!secure) return OFF('needs-https')

  const { createAuth0Client } = await load()
  const client = await createAuth0Client({
    domain: config.domain,
    clientId: config.client_id,
    authorizationParams: { audience: config.audience, redirect_uri: location.origin },
    cacheLocation: 'localstorage',
    useRefreshTokens: true,
  })

  // Coming back from Auth0: finish the sign-in and tidy the address.
  const query = new URLSearchParams(location.search)
  if (query.has('state') && (query.has('code') || query.has('error'))) {
    try {
      await client.handleRedirectCallback()
    } catch {
      // a stale or refused sign-in: stay signed out
    }
    history.replaceState(null, '', `${location.pathname}#settings`)
  }

  const auth = {
    enabled: true,
    signedIn: await client.isAuthenticated(),
    signIn: () => client.loginWithRedirect(),
    signOut: () => client.logout({ logoutParams: { returnTo: location.origin } }),
    token: async () => {
      if (!auth.signedIn) return ''
      try {
        return await client.getTokenSilently()
      } catch {
        auth.signedIn = false // the session ran out
        return ''
      }
    },
  }
  return auth
}

// A goat name from a fingerprint: something to call yourself that is not you.
const BOLD = ['Brave', 'Quiet', 'Bold', 'Swift', 'Gentle', 'Merry', 'Steady', 'Wild', 'Kind', 'Sunny', 'Misty', 'Lucky', 'Nimble', 'Proud', 'Curious', 'Calm']
const TREE = ['Cedar', 'Maple', 'Birch', 'Aspen', 'Willow', 'Juniper', 'Spruce', 'Hazel', 'Alder', 'Larch', 'Clover', 'Fern', 'Thistle', 'Moss', 'Pine', 'Sage']

export function goatName(fingerprint) {
  const hex = String(fingerprint || '').toLowerCase()
  if (!/^[0-9a-f]{4,}$/.test(hex)) return 'A goat'
  return `${BOLD[parseInt(hex[0], 16)]} ${TREE[parseInt(hex[1], 16)]} Goat`
}
