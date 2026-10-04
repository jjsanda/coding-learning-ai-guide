import { test, expect, type APIRequestContext } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Drives a seeded demo stack and saves documentation screenshots to
// docs/images. Required env: CODEGUIDE_INSTRUCTOR_TOKEN (from `make seed`).
//
//   BASE_URL=http://localhost:8080 \
//   CODEGUIDE_INSTRUCTOR_TOKEN=cgi_... \
//   npx playwright test e2e/screenshots.spec.ts

const OUT = resolve(__dirname, '../../docs/images')
const TOKEN = process.env.CODEGUIDE_INSTRUCTOR_TOKEN

async function firstCourseJoinCode(request: APIRequestContext): Promise<string> {
  const resp = await request.get('/api/v1/courses', {
    headers: { Authorization: `Bearer ${TOKEN}` },
  })
  const courses = await resp.json()
  return courses[0].join_code
}

async function firstCourseId(request: APIRequestContext): Promise<string> {
  const resp = await request.get('/api/v1/courses', {
    headers: { Authorization: `Bearer ${TOKEN}` },
  })
  const courses = await resp.json()
  return courses[0].id
}

test.beforeAll(() => {
  if (!TOKEN) throw new Error('Set CODEGUIDE_INSTRUCTOR_TOKEN (run `make seed` first)')
  mkdirSync(OUT, { recursive: true })
})

test('instructor dashboard', async ({ page, request }) => {
  const courseId = await firstCourseId(request)
  await page.addInitScript((token) => {
    localStorage.setItem('clag.instructor', token as string)
  }, TOKEN)
  await page.goto(`/instructor/courses/${courseId}`)
  await expect(page.getByText('Class insights')).toBeVisible()
  await page.waitForTimeout(1500) // let the charts finish animating
  await page.screenshot({ path: `${OUT}/instructor-dashboard.png`, fullPage: true })
})

test('student submission and feedback', async ({ page, request }) => {
  const joinCode = await firstCourseJoinCode(request)

  await page.goto('/join')
  await page.getByPlaceholder('ABCD1234').fill(joinCode)
  await page.getByPlaceholder('Ada Lovelace').fill('Sam Student')
  await page.getByRole('button', { name: 'Join course' }).click()

  await expect(page.getByRole('heading', { name: 'Assignments' })).toBeVisible()
  await page.getByText('Safe user lookup').click()

  await expect(page.getByText('Your solution')).toBeVisible()
  await page.screenshot({ path: `${OUT}/assignment-detail.png`, fullPage: true })

  // Type a deliberately vulnerable solution to produce rich feedback.
  const editor = page.locator('.cm-content')
  await editor.click()
  await page.keyboard.insertText(
    'import sqlite3\npassword = "hunter2"\nname = input().strip()\n' +
      'conn = sqlite3.connect(":memory:")\ncur = conn.cursor()\n' +
      'cur.execute("CREATE TABLE users (name TEXT, role TEXT)")\n' +
      'cur.execute("INSERT INTO users VALUES (\'ada\', \'admin\')")\n' +
      'cur.execute(f"SELECT role FROM users WHERE name = \'{name}\'")\n' +
      'row = cur.fetchone()\nprint(row[0] if row else "unknown")\n',
  )
  await page.getByRole('button', { name: 'Submit for feedback' }).click()

  await expect(page.getByRole('heading', { name: 'Feedback' })).toBeVisible({ timeout: 90_000 })
  // Wait for the async feedback content (not just the static heading) to render.
  await expect(page.getByText(/Feedback is formative/)).toBeVisible({ timeout: 30_000 })
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${OUT}/student-feedback.png`, fullPage: true })
})
