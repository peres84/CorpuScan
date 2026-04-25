import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import BottomCta from "@/components/BottomCta";
import Footer from "@/components/Footer";

const Landing = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Nav />
      <main className="flex-1">
        <Hero />
        <HowItWorks />
        <BottomCta />
      </main>
      <Footer />
    </div>
  );
};

export default Landing;
