import { ChevronLeft, ChevronRight } from "lucide-react";

const pageSizes = [10, 20, 40] as const;

type QueuePaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

function visiblePages(page: number, totalPages: number): Array<number | string> {
  const pages = [...new Set([1, page - 1, page, page + 1, totalPages])]
    .filter((value) => value >= 1 && value <= totalPages)
    .sort((left, right) => left - right);
  const result: Array<number | string> = [];
  pages.forEach((value, index) => {
    const previous = pages[index - 1];
    if (previous && value - previous > 1) result.push(`gap-${previous}`);
    result.push(value);
  });
  return result;
}

export function QueuePagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: QueuePaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const firstItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, total);

  return (
    <div className="queue-pagination">
      <label>
        <span>Постов на странице</span>
        <select
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          aria-label="Количество постов на странице"
        >
          {pageSizes.map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
      </label>

      <span className="queue-pagination-summary">
        {firstItem}–{lastItem} из {total}
      </span>

      <nav aria-label="Страницы очереди">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Предыдущая страница"
        >
          <ChevronLeft size={17} />
        </button>
        {visiblePages(page, totalPages).map((value) => typeof value === "number" ? (
          <button
            type="button"
            key={value}
            className={value === page ? "active" : ""}
            onClick={() => onPageChange(value)}
            aria-current={value === page ? "page" : undefined}
          >
            {value}
          </button>
        ) : <span key={value}>…</span>)}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Следующая страница"
        >
          <ChevronRight size={17} />
        </button>
      </nav>
    </div>
  );
}
