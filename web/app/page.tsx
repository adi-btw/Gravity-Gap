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
      </section>
      <HomePicker />
    </div>
  );
}
