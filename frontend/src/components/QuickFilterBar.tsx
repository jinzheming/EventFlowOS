import { ItemQuickFilter, quickFilterLabels } from '../lib/itemFilters';

export function QuickFilterBar({
  value,
  options,
  onChange,
}: {
  value: ItemQuickFilter;
  options: ItemQuickFilter[];
  onChange: (filter: ItemQuickFilter) => void;
}) {
  return (
    <div className="segmented-control quick-filter-bar" aria-label="快捷过滤">
      {options.map((option) => (
        <button
          className={value === option ? 'chip active' : 'chip'}
          type="button"
          key={option}
          onClick={() => onChange(option)}
        >
          {quickFilterLabels[option]}
        </button>
      ))}
    </div>
  );
}
