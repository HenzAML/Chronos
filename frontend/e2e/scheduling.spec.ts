import { expect, test, type Page } from '@playwright/test'
import { seed } from './env.ts'

async function generate(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Generate schedule' }).click()
  return page.locator('.alert').filter({ hasText: /Schedule #\d+|No timetable produced/ })
}

test('happy path: every class is placed and shown on the timetable', async ({ page }) => {
  seed('--tight')
  const result = await generate(page)

  await expect(result).toContainText(/generated — (optimal|feasible)/)
  await expect(result).toContainText('82 of 82 classes placed')
  await expect(result.locator('.unscheduled')).toHaveCount(0)

  await result.getByRole('button', { name: 'Open timetable' }).click()
  await expect(page.locator('table.timetable')).toBeVisible()
  await expect(page.locator('.summary')).toContainText('82 / 82')
  await expect(page.getByText('could not be scheduled')).toHaveCount(0)
  // 82 classes, each drawn once at its start hour.
  await expect(page.locator('.event:not(.event-cont)')).toHaveCount(82)
})

test('unhappy path: best timetable plus a reason for every class left out', async ({ page }) => {
  seed('--conflict')
  const result = await generate(page)

  await expect(result).toContainText('best timetable found, 7 of 93 classes left out')
  await expect(result).toContainText('86 of 93 classes placed')
  await expect(result.locator('.unscheduled > li')).toHaveCount(7)

  const reason = (code: string) => result.locator('.unscheduled > li').filter({ hasText: code })
  await expect(reason('DEMO901')).toContainText('Room too small')
  await expect(reason('DEMO901')).toContainText('200')
  await expect(reason('DEMO902')).toContainText('Missing equipment')
  await expect(reason('DEMO903')).toContainText('Class too long')
  await expect(reason('DEMO904')).toContainText('Instructor availability')
  await expect(reason('DEMO905')).toContainText('Needs another day')

  await result.getByRole('button', { name: 'Open timetable' }).click()
  const warning = page.locator('.alert-warn')
  await expect(warning).toContainText('7 of 93 classes could not be scheduled')
  await expect(warning.locator('.unscheduled > li')).toHaveCount(7)
  await expect(page.locator('.summary')).toContainText('partial')

  // The placed classes are still there, multi-hour ones continued in later hours.
  await expect(page.locator('.event:not(.event-cont)')).toHaveCount(86)
  await expect(page.locator('.event-cont').first()).toContainText('cont.')

  await page.locator('.event:not(.event-cont)').first().click()
  await expect(page.locator('.detail')).toContainText('Instructor')
})

test('a course added in the website that fits no room is left out with the reason', async ({ page }) => {
  seed('--tight')
  await page.goto('/courses')
  await page.getByRole('button', { name: 'New course' }).click()
  await page.getByLabel('Code').fill('E2E500')
  await page.getByLabel('Name').fill('Whole Faculty Assembly')
  await page.getByLabel('Expected students').fill('500')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByRole('cell', { name: 'E2E500' })).toBeVisible()

  const result = await generate(page)
  await expect(result).toContainText('1 of 83 classes left out')
  const left = result.locator('.unscheduled > li')
  await expect(left).toHaveCount(1)
  await expect(left).toContainText('E2E500')
  await expect(left).toContainText('Room too small')
  await expect(left).toContainText('500')
})
