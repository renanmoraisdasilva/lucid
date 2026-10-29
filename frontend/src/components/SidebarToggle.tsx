export function SidebarToggle({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      aria-label="Open navigation"
      aria-controls="app-sidebar"
      onClick={onOpen}
      className="-ml-1 rounded-md p-1.5 text-[15px] leading-none text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary lg:hidden"
    >
      <span aria-hidden="true">☰</span>
    </button>
  );
}
