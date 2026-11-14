import { expect, test, type Locator, type Page } from '@playwright/test'
import { seed } from './env.ts'

async function generate(page: Page) {
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await page.getByRole('button', { name: 'Generate schedule' }).click()
  return page.locator('.alert').filter({ hasText: /Schedule #\d+|No timetable produced/ })
}

const leftOut = (result: Locator, code: string) =>
  result.locator('.unscheduled > li').filter({ hasText: code })

test('rooms: adding a big enough room gets the oversized class placed', async ({ page }) => {
  seed('--conflict')        // DEMO901 has 200 students; the largest room seats 120
  await page.goto('/rooms')
  await page.getByRole('button', { name: 'New room' }).click()
  await page.getByLabel('Code').fill('BIG-1')
  await page.getByLabel('Name').fill('Auditorium')
  await page.getByLabel('Capacity').fill('250')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByRole('row').filter({ hasText: 'BIG-1' })).toContainText('250')

  const result = await generate(page)
  await expect(result).toContainText('6 of 93 classes left out')
  await expect(leftOut(result, 'DEMO901')).toHaveCount(0)
  await expect(leftOut(result, 'DEMO902')).toHaveCount(1)
})

test('rooms: edit and delete', async ({ page }) => {
  seed('--tight')
  await page.goto('/rooms')
  const rows = page.locator('table.table tbody tr')
  await expect(rows).toHaveCount(9)

  await rows.first().getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel('Capacity').fill('77')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(rows.first().getByRole('cell', { name: '77', exact: true })).toBeVisible()

  page.once('dialog', (d) => d.accept())
  await rows.first().getByRole('button', { name: 'Delete' }).click()
  await expect(rows).toHaveCount(8)
})

test('instructors: widening availability removes the availability reason', async ({ page }) => {
  seed('--conflict')        // Dr. Demo Gaps is free Mon/Wed 09:00 and 11:00 only; DEMO904 needs 2 hours
  await page.goto('/instructors')
  const row = page.getByRole('row').filter({ hasText: 'Dr. Demo Gaps' })
  await expect(row.getByRole('cell').nth(4)).toHaveText('4')

  await row.getByRole('button', { name: 'Edit' }).click()
  for (const day of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']) {
    // The day header ticks the whole day when any slot of it is missing.
    await page.locator('table.availability').getByRole('button', { name: day, exact: true }).click()
  }
  await expect(page.getByText('Availability — 30 slot(s) selected')).toBeVisible()
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(row.getByRole('cell').nth(4)).toHaveText('30')

  const result = await generate(page)
  await expect(result).toContainText(/\d+ of 93 classes left out/)
  await expect(leftOut(result, 'DEMO904').getByText('Instructor availability')).toHaveCount(0)
})

test('instructors: create with preferences, then delete', async ({ page }) => {
  seed('--tight')
  await page.goto('/instructors')
  await page.getByRole('button', { name: 'New instructor' }).click()
  await page.getByLabel('Name').fill('Dr. E2E Tester')
  await page.getByLabel('Email').fill('e2e@example.com')
  await page.getByLabel('Prefers mornings (before 12:00)').check()
  await page.getByRole('button', { name: 'Mon 9:00', exact: true }).click()
  await page.getByRole('button', { name: 'Mon 10:00', exact: true }).click()
  // Clicking a group's caption must not press a control inside it.
  await page.getByText('Availability — 2 slot(s) selected').click()
  await expect(page.getByText('Availability — 2 slot(s) selected')).toBeVisible()
  await page.getByRole('button', { name: 'Save' }).click()

  const row = page.getByRole('row').filter({ hasText: 'Dr. E2E Tester' })
  await expect(row.getByRole('cell').nth(2)).toHaveText('Yes')
  await expect(row.getByRole('cell').nth(4)).toHaveText('2')

  page.once('dialog', (d) => d.accept())
  await row.getByRole('button', { name: 'Delete' }).click()
  await expect(row).toHaveCount(0)
})

test('constraints: switching the capacity rule off lets the oversized class in', async ({ page }) => {
  seed('--conflict')
  await page.goto('/constraints')
  await page.getByLabel(/Room capacity/).uncheck()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()

  await page.reload()
  await expect(page.getByLabel(/Room capacity/)).not.toBeChecked()

  const result = await generate(page)
  await expect(result).toContainText(/\d+ of 93 classes left out/)
  await expect(leftOut(result, 'DEMO901')).toHaveCount(0)
  await expect(leftOut(result, 'DEMO902')).toHaveCount(1)
})

test('constraints: weights save, and preview shows a partial result', async ({ page }) => {
  seed('--conflict')
  await page.goto('/constraints')
  const morning = page.locator('.slider-row').filter({ hasText: 'Morning preference' })
  await morning.locator('input[type=range]').fill('0')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible()
  await page.reload()
  await expect(morning.locator('output')).toHaveText('0')

  await page.getByRole('button', { name: 'Preview effect' }).click()
  const preview = page.locator('.alert').filter({ hasText: 'Preview: Z =' })
  await expect(preview).toContainText('86 of 93 classes placed')
  await expect(preview.getByRole('row').filter({ hasText: 'S1 mornings' }).getByRole('cell').nth(1))
    .toHaveText('0')
})

test('failed run: courses but no rooms gives a message, not a crash', async ({ page }) => {
  seed('--tight')
  for (const r of await (await page.request.get('/api/rooms')).json()) {
    expect((await page.request.delete(`/api/rooms/${r.id}`)).ok()).toBe(true)
  }
  await page.goto('/')
  const result = await generate(page)
  await expect(result).toContainText('No timetable produced')
  await expect(result).toContainText('no rooms defined')
  await expect(result.getByRole('button', { name: 'Open timetable' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Timetable' }).click()
  await expect(page.getByText('No timetable was produced')).toBeVisible()
  await expect(page.locator('table.timetable')).toHaveCount(0)
})

test('empty catalogue: nothing to generate, pages show empty states', async ({ page }) => {
  seed('--tight')
  for (const c of await (await page.request.get('/api/courses')).json()) {
    expect((await page.request.delete(`/api/courses/${c.id}`)).ok()).toBe(true)
  }
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Generate schedule' })).toBeDisabled()
  await expect(page.getByText('Nothing generated yet.')).toBeVisible()

  await page.getByRole('link', { name: 'Timetable' }).click()
  await expect(page.getByText('No schedules yet.')).toBeVisible()
  await page.getByRole('link', { name: 'Courses' }).click()
  await expect(page.getByText('No courses match.')).toBeVisible()
})

test('API down: the page shows an error with a retry, not a blank screen', async ({ page }) => {
  // By path, not '**/api/**': that glob also matches Vite's /src/api/client.ts.
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => route.abort())
  await page.goto('/')
  await expect(page.locator('.alert-error')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})
