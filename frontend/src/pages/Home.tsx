import { Link } from 'react-router-dom'
import { Layout } from '../components/Layout'

export function Home() {
  return (
    <Layout>
      <div className="mx-auto max-w-2xl text-center">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Formative code feedback for programming courses
        </h1>
        <p className="mt-4 text-lg text-slate-600">
          Submit your code, and get feedback on correctness, style, complexity and security —
          grounded in real analyzers, explained so you can fix it yourself.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            to="/join"
            className="rounded-lg bg-sky-600 px-5 py-2.5 font-medium text-white hover:bg-sky-700"
          >
            I'm a student — join a course
          </Link>
          <Link
            to="/instructor"
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-700 hover:bg-slate-50"
          >
            I'm an instructor
          </Link>
        </div>
      </div>
    </Layout>
  )
}
