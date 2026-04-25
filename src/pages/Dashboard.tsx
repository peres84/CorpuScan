import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import GenerateForm from "@/components/GenerateForm";

const Dashboard = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Nav />
      <main className="flex-1 px-6 pb-16">
        <GenerateForm />
      </main>
      <Footer />
    </div>
  );
};

export default Dashboard;
