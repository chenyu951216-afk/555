import { ReactNode } from "react";
import { clsx } from "clsx";

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-sm text-graphite">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={clsx("rounded-md border border-line bg-white p-4 shadow-soft", className)}>{children}</section>;
}

export function StatCard({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="text-xs text-graphite">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {detail ? <div className="mt-1 text-xs text-graphite">{detail}</div> : null}
    </div>
  );
}

export function Button({ children, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={clsx(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium transition hover:border-teal disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx("h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-teal", className)} {...props} />;
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={clsx("h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-teal", className)} {...props} />;
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center rounded border border-line bg-paper px-2 py-0.5 text-xs text-graphite">{children}</span>;
}

export function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-line bg-white p-6 text-center text-sm text-graphite">{text}</div>;
}

export function LoadingState() {
  return <div className="rounded-md border border-line bg-white p-6 text-sm text-graphite">資料載入中，若超過 30 秒會顯示連線錯誤。</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="rounded-md border border-rose/40 bg-white p-4 text-sm text-rose">{message}</div>;
}
