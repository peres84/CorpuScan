interface Step {
  num: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  { num: "01", title: "Upload", body: "Drop a quarterly report PDF, paste a URL, or search a query." },
  { num: "02", title: "Extract", body: "A finance agent finds the signal in the noise." },
  { num: "03", title: "Narrate", body: "A scripter agent writes a 4-scene voiceover." },
  { num: "04", title: "Render", body: "Motion graphics and voice combine into a 2-minute video." },
];

export const HowItWorks = () => {
  return (
    <section id="how" className="max-w-6xl mx-auto px-6 py-24">
      <h2 className="text-3xl font-semibold text-primary">How it works</h2>
      <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {STEPS.map((step) => (
          <div
            key={step.num}
            className="bg-surface border border-gray-200 rounded-2xl p-6 shadow-sm"
          >
            <p className="font-mono text-accent text-sm">{step.num}</p>
            <h3 className="mt-3 text-lg font-semibold text-primary">{step.title}</h3>
            <p className="mt-2 text-secondary text-sm leading-relaxed">{step.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default HowItWorks;
