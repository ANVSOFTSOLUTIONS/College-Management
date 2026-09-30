// Sample content for template previews (marketing page and the template picker
// before a college has added its own). Clearly placeholder college details.
const photo = (id, w = 1600) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=70`;

export const SAMPLE_SITE = {
  name: "Green Valley College of Engineering",
  code: "SAMPLE",
  tagline: "Autonomous institution offering engineering, management and computer applications.",
  established: "1998",
  accreditation: "NAAC A+ | NBA accredited | AICTE approved | Affiliated to JNTUA",
  highlights: [
    { value: "27+", label: "Years of excellence" },
    { value: "4,200+", label: "Students" },
    { value: "92%", label: "Placement record" },
    { value: "180+", label: "Faculty members" },
  ],
  programs: [
    { name: "B.Tech Computer Science", level: "UG", duration: "4 years", seats: "240", description: "AI, data science and full-stack development with industry projects." },
    { name: "B.Tech Electronics & Communication", level: "UG", duration: "4 years", seats: "120", description: "VLSI, embedded systems and IoT labs." },
    { name: "B.Tech Mechanical", level: "UG", duration: "4 years", seats: "60", description: "Design, manufacturing and robotics." },
    { name: "M.Tech Data Science", level: "PG", duration: "2 years", seats: "18", description: "Machine learning, big data and research." },
    { name: "MBA", level: "PG", duration: "2 years", seats: "120", description: "Finance, marketing, HR and business analytics." },
    { name: "MCA", level: "PG", duration: "2 years", seats: "60", description: "Software engineering and cloud computing." },
  ],
  departments: [
    { name: "Computer Science & Engineering", code: "CSE" },
    { name: "Electronics & Communication", code: "ECE" },
    { name: "Mechanical Engineering", code: "MECH" },
    { name: "Business Administration", code: "MBA" },
  ],
  placements: {
    recruiters: ["TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "HCLTech", "Capgemini", "Amara Raja", "Zoho", "Deloitte"],
    students_placed: 612,
    highest_package: 18.5,
    average_package: 4.8,
  },
  principal_name: "Dr. K. Srinivasa Rao",
  principal_title: "Principal",
  principal_message:
    "Welcome to Green Valley College of Engineering. For over two decades we have prepared young people not just for jobs, but for lives of purpose and leadership.\n\nOur faculty, laboratories and industry partnerships give every student the chance to learn by doing. I invite you to visit our campus and see it for yourself.",
  logo_url: null,
  banners: [
    { id: "b1", url: photo("photo-1580582932707-520aed937b7b"), caption: "Learn, build and lead." },
    { id: "b2", url: photo("photo-1427504494785-3a9ca7044f45"), caption: "Admissions open for B.Tech, MBA and MCA 2026-27." },
    { id: "b3", url: photo("photo-1509062522246-3755977927d7"), caption: "Industry-ready graduates, experienced faculty." },
  ],
  about:
    "Green Valley College of Engineering offers B.Tech, M.Tech, MBA and MCA programs with experienced faculty, modern laboratories, a digital library, hostels and a dedicated training & placement cell.\n\nOur students work on real projects, internships and research from their first year, and go on to careers with leading companies.",
  contact: { address: "Plot 12, Main Road, Your City", phone: "+91 90000 00000", email: "info@yourcollege.example", map_url: "" },
  gallery: [
    { id: "g1", url: photo("photo-1503676260728-1c00da094a0b", 900), caption: "Lecture hall" },
    { id: "g2", url: photo("photo-1532094349884-543bc11b234d", 900), caption: "Engineering lab" },
    { id: "g3", url: photo("photo-1497633762265-9d179a990aa6", 900), caption: "Central library" },
    { id: "g4", url: photo("photo-1571260899304-425eee4c7efc", 900), caption: "Campus" },
    { id: "g5", url: photo("photo-1546410531-bb4caa6b424d", 900), caption: "Tech fest" },
    { id: "g6", url: photo("photo-1577896851231-70ef18881754", 900), caption: "Sports meet" },
  ],
  activities: [
    { id: "a1", title: "Annual Sports Meet", date: "2026-11-14", description: "Inter-department cricket, athletics and indoor games." },
    { id: "a2", title: "Project Expo", date: "2026-10-22", description: "Final-year teams demonstrate their projects to industry judges." },
    { id: "a3", title: "Cultural & Tech Fest", date: "2026-12-05", description: "Hackathon, paper presentations, music and dance." },
  ],
  notices: [
    { id: "n1", title: "Admissions open for the new academic year", date: "2026-10-01" },
    { id: "n2", title: "Campus placement drive: 12 companies this month", date: "2026-09-26" },
    { id: "n3", title: "Mid-1 examinations begin next Monday", date: "2026-09-20" },
  ],
};
