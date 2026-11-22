import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Landing, { readStarted } from './Landing.jsx'

const serviceWith = (account) => ({ account: account ? async () => account : undefined })

describe('the landing page', () => {
  beforeEach(() => window.sessionStorage.clear())
  afterEach(cleanup)

  it('says Start when the server has no accounts', async () => {
    const onStart = vi.fn()
    render(<Landing service={serviceWith({ enabled: false, signedIn: false })} onStart={onStart} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start' }))
    expect(onStart).toHaveBeenCalled()
    expect(readStarted()).toBe(true)
  })

  it('says Start in the demo story, which has no accounts at all', async () => {
    render(<Landing service={serviceWith(null)} onStart={() => {}} />)
    expect(await screen.findByRole('button', { name: 'Start' })).toBeTruthy()
  })

  it('says Log in when Auth0 is set up, and still lets you in without an account', async () => {
    const signIn = vi.fn()
    const onStart = vi.fn()
    render(<Landing service={serviceWith({ enabled: true, signedIn: false, signIn })} onStart={onStart} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Log in' }))
    expect(signIn).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Just look around' }))
    expect(onStart).toHaveBeenCalled()
  })

  it('lets someone already signed in straight through', async () => {
    const onStart = vi.fn()
    render(<Landing service={serviceWith({ enabled: true, signedIn: true })} onStart={onStart} />)
    await waitFor(() => expect(onStart).toHaveBeenCalled())
  })
})
