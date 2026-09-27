import { ChevronLeft, ChevronRight } from "lucide-react";

type Props = {
  pageNumber: number; count: number; limit: number; label: string;
  canPrevious: boolean; canNext: boolean; previous: () => void; next: () => void;
};

export function JournalPagination({ pageNumber, count, limit, label, canPrevious, canNext, previous, next }: Props) {
  const offset = (pageNumber - 1) * limit;
  return <div className="log-pagination">
    <span>{label} {count ? offset + 1 : 0}–{count ? offset + count : 0}</span>
    <div>
      <button className="icon-button" aria-label="Предыдущая страница" disabled={!canPrevious} onClick={previous}><ChevronLeft size={17} /></button>
      <strong>Страница {pageNumber}</strong>
      <button className="icon-button" aria-label="Следующая страница" disabled={!canNext} onClick={next}><ChevronRight size={17} /></button>
    </div>
  </div>;
}
