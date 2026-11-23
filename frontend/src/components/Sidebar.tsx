interface Props {
  total: number | null // null while loading
}

/**
 * Views on the left (only "All" for now; story 3.5 adds Unclassified, Classified,
 * each priority and Trash, with counts). Hidden on narrow screens.
 */
export function Sidebar({ total }: Props) {
  return (
    <nav aria-label="Views" className="hidden w-52 shrink-0 border-r border-gray-200 p-3 md:block">
      <ul>
        <li>
          <button
            type="button"
            aria-current="page"
            className="flex w-full items-center justify-between rounded-md bg-blue-50 px-3 py-1.5 text-sm font-semibold text-blue-800"
          >
            <span>All</span>
            <span>{total ?? ''}</span>
          </button>
        </li>
      </ul>
    </nav>
  )
}
