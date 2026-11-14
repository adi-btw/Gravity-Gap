import Link from "next/link";
import { HomePicker } from "@/components/HomePicker";

export default function Home() {
  return (
    <div className="space-y-6">
      <section>
        <p className="text-xs uppercase tracking-wider text-micro">Partial-gravity fire prediction</p>
        <h1 className="mt-1 max-w-4xl text-3xl font-semibold leading-tight">
          NASA has hundreds of fire tests in orbit and on Earth, but none at the Moon&apos;s or Mars&apos; gravity,
          where crews will live next.
        </h1>
        <p className="mt-2 max-w-3xl text-muted">
          Gravity Gap bridges that gap with transparent scaling laws and tells you which evidence applies to your
          habitat, with honest uncertainty.
        </p>
        <p className="mt-3">
          <Link
            href="/replay"
            className="inline-flex items-center gap-1 rounded-md border border-normal px-3 py-1.5 text-sm text-normal hover:bg-surface-2"
          >
            Start with a real fire <span aria-hidden="true">→</span>
          </Link>
          <span className="ml-3 text-xs text-muted">
            The conditions of real spacecraft fires, and what today&apos;s data can and cannot say about them.
          </span>
        </p>
      </section>
      <HomePicker />
    </div>
  );
}
