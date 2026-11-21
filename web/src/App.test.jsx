// The page against the contract. Run with: npm test
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import example from '../../contract/examples/state.json'
import { View } from './App.jsx'

afterEach(cleanup)

test('draws the contract example state', () => {
  const { container } = render(<View state={example} status="live" />)
  expect(screen.getByText('Scrambler')).toBeTruthy()
  expect(screen.getByText(/80 XP · 70 to the next stage/)).toBeTruthy()
  expect(screen.getByText('Find a water bottle at your table')).toBeTruthy()
  expect(screen.getByText('1 of 79 found')).toBeTruthy()
  expect(screen.getByText('+80 XP')).toBeTruthy()
  expect(screen.getByText(/named on the device in 41 ms/)).toBeTruthy()
  expect(screen.getByText('Live')).toBeTruthy()

  // The map is always 5 x 5: known places, then fog.
  const tiles = container.querySelectorAll('.tile')
  expect(tiles.length).toBe(25)
  expect(container.querySelector('.tile.cleared').textContent).toBe('Harris Park')
  expect(container.querySelectorAll('.tile.fog.named').length).toBe(2)

  // Herds are listed; "you" is highlighted.
  expect(container.querySelector('.cup li.you').textContent).toContain('Your herd')
  expect(screen.getByText(/people are never ranked/)).toBeTruthy()
})

test('a fresh Gary naps, with no guilt and no quest pressure', () => {
  const fresh = {
    ...example,
    gary: { stage: 'kid', stage_index: 0, xp: 0, stage_xp: 0, next_stage_xp: 60, napping: true, welcome_back: false },
    journal: [],
    guide: { total: 79, found: [] },
  }
  render(<View state={fresh} status="mock" />)
  expect(screen.getByText('Kid')).toBeTruthy()
  expect(screen.getByText(/Gary is napping. No guilt/)).toBeTruthy()
  expect(screen.getByLabelText('Gary, napping')).toBeTruthy()
  expect(screen.getByText('0 of 79 found')).toBeTruthy()
  expect(screen.getByText(/Nothing yet/)).toBeTruthy()
  expect(screen.getByText(/Mock data/)).toBeTruthy()
})

test('the last stage and an empty quest list do not break the page', () => {
  const top = {
    ...example,
    gary: { ...example.gary, stage: 'summit-elder', stage_index: 3, xp: 400, stage_xp: 300, next_stage_xp: null },
    quest: null,
    quests_open: 0,
  }
  render(<View state={top} status="stale" />)
  expect(screen.getByText('Summit Elder')).toBeTruthy()
  expect(screen.getByText(/top of the mountain/)).toBeTruthy()
  expect(screen.getByText(/Every quest is done/)).toBeTruthy()
  expect(screen.getByText(/Backend unreachable/)).toBeTruthy()
})
