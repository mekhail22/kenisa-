import React, { useState, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, 
  Users, 
  CalendarRange, 
  DollarSign, 
  MessageSquare, 
  BarChart3, 
  ShieldAlert, 
  Sun, 
  Moon, 
  Globe, 
  Menu, 
  X, 
  ChevronLeft, 
  PlusCircle, 
  Sparkles, 
  Clock, 
  UserCheck, 
  Activity, 
  Info, 
  Search, 
  Filter, 
  Plus, 
  CheckCircle, 
  Trash2, 
  Tag, 
  ArrowRight, 
  RefreshCw, 
  Eye, 
  Share2, 
  Award, 
  Download, 
  Camera, 
  AlertCircle,
  MapPin,
  ShieldCheck,
  CheckCircle2,
  Bookmark,
  ArrowLeft,
  ArrowDownLeft,
  ArrowUpRight,
  TrendingUp,
  FileText,
  Printer,
  Pin,
  Bell,
  Send,
  Heart,
  Star,
  HelpCircle
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend, PieChart, Pie, Cell, LineChart, Line } from 'recharts';

// ==========================================
// 1. DATA MODELS & TYPES DEFINITIONS
// ==========================================

export interface User {
  id: string;
  name: string;
  role: 'Admin' | 'Father' | 'Servant' | 'Visitor';
  avatar: string;
  email: string;
  phone: string;
}

export interface Member {
  id: string;
  fullName: string;
  fullNameEn?: string;
  age: number;
  gender: 'ذكر' | 'أنثى';
  phone: string;
  parentPhone?: string;
  email?: string;
  address: string;
  service: string; // e.g. "إعداد خدام", "ثانوي", "جامعي", "أطفال"
  status: 'نشط' | 'غير نشط' | 'متردد' | 'خادم';
  avatar: string;
  qrCode: string;
  familyId: string; // For family tree grouping
  familyRole: 'أب' | 'أم' | 'ابن' | 'ابنة' | 'جد' | 'جدة';
  joinDate: string;
  tags: string[];
}

export interface AttendanceRecord {
  id: string;
  memberId: string;
  memberName: string;
  date: string; // YYYY-MM-DD
  status: 'حاضر' | 'غائب' | 'متأخر' | 'مستأذن';
  notes?: string;
}

export interface ChurchEvent {
  id: string;
  title: string;
  titleEn?: string;
  date: string; // YYYY-MM-DD
  time: string;
  location: string;
  description: string;
  rsvpCount: number;
  expectedAttendance: number;
  capacity: number;
  resourceBooked?: string;
}

export interface Expense {
  id: string;
  title: string;
  category: 'صيانة' | 'مساعدات' | 'أنشطة' | 'أجور' | 'أخرى';
  amount: number;
  date: string;
  recordedBy: string;
  receiptNumber: string;
  notes?: string;
}

export interface Donation {
  id: string;
  donorName: string;
  amount: number;
  category: 'عشور' | 'بكور' | 'تبرع عام' | 'إخوة الرب';
  date: string;
  paymentMethod: 'نقدي' | 'فيزا' | 'محفظة إلكترونية' | 'حوالة';
  receiptNumber: string;
}

export interface PrayerRequest {
  id: string;
  name: string;
  request: string;
  date: string;
  status: 'مرفوعة' | 'جديدة' | 'مستجابة';
  supportersCount: number;
  supportedBy: string[]; // List of user IDs
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  date: string;
  pinned: boolean;
  author: string;
  category: 'عام' | 'خدمات' | 'اجتماعات' | 'مفقودات';
}

export interface ChatMessage {
  id: string;
  senderName: string;
  senderRole: string;
  senderAvatar: string;
  content: string;
  timestamp: string;
  pinned?: boolean;
}

export interface AuditLog {
  id: string;
  userId: string;
  userName: string;
  action: string;
  details: string;
  timestamp: string;
}

export interface ResourceBooking {
  id: string;
  resourceName: string; // e.g. "القاعة الكبرى", "مسرح الكنيسة", "جهاز بروجيكتور"
  bookedBy: string;
  date: string;
  timeSlot: string;
  status: 'مؤكد' | 'قيد الانتظار' | 'ملغي';
}

// ==========================================
// 2. MULTILINGUAL TRANSLATIONS
// ==========================================

export type Language = 'ar' | 'en' | 'cop';

export const translations = {
  ar: {
    title: "نظام إدارة كنيسة الشهيدة دميانة",
    subtitle: "نظام الإدارة والخدمة الذكية المتكامل",
    dashboard: "لوحة التحكم",
    members: "إدارة الأعضاء",
    events: "الفعاليات والحجوزات",
    finance: "إدارة المالية",
    communication: "التواصل الداخلي",
    reports: "التقارير والتحليلات",
    security: "الأمان والرقابة",
    welcome: "أهلاً بك يا",
    activeRole: "الصلاحية الحالية",
    totalMembers: "إجمالي الأعضاء",
    activeMembers: "الأعضاء النشطين",
    upcomingEvents: "الفعاليات القادمة",
    totalBudget: "الميزانية العامة",
    searchPlaceholder: "البحث عن الأعضاء بالاسم، الهاتف، أو الكود...",
    familyTree: "شجرة عائلة كنسية",
    prayerRequests: "طلبات الصلاة والطلبات المباركة",
    donations: "العطاء الرقمي والتبرعات",
    expenses: "تسجيل وحساب المصروفات",
    auditLogs: "سجل الأنشطة والرقابة",
    copticGreeting: "اونه أوفري! (يوم سعيد)"
  },
  en: {
    title: "St. Demiana Church Management System",
    subtitle: "Integrated Church & Service System",
    dashboard: "Dashboard",
    members: "Member Management",
    events: "Events & Bookings",
    finance: "Finance Hub",
    communication: "Internal Comms",
    reports: "Reports & Analytics",
    security: "Security & Auditing",
    welcome: "Welcome,",
    activeRole: "Current Role",
    totalMembers: "Total Members",
    activeMembers: "Active Members",
    upcomingEvents: "Upcoming Events",
    totalBudget: "Total Budget",
    searchPlaceholder: "Search members by name, phone, or code...",
    familyTree: "Ecclesial Family Tree",
    prayerRequests: "Blessed Prayer Requests",
    donations: "Digital Giving & Offerings",
    expenses: "Expense Ledger",
    auditLogs: "Audit & Access Logs",
    copticGreeting: "Nofri! (Good Day)"
  },
  cop: {
    title: "ⲡⲓⲥⲩⲥⲧⲏⲙⲁ ̀ⲛⲧⲉ ̀ⲧⲁⲅⲓⲁ Ⲇⲏⲙⲓⲁⲛⲏ",
    subtitle: "ⲡⲓⲥⲩⲥⲧⲏⲙⲁ ̀ⲛⲧⲉ ϯⲉⲕⲕⲗⲏⲥⲓⲁ ⲛⲉⲙ ⲡⲓϣⲉⲙϣⲓ",
    dashboard: "ⲡⲓⲡⲓⲛⲁⲝ",
    members: "ⲛⲓⲙⲉⲗⲟⲥ",
    events: "ⲛⲓϣⲁⲓ ⲛⲉⲙ ⲛⲓⲧⲟⲡⲟⲥ",
    finance: "ⲡⲓⲥⲱⲃⲉ ̀ⲛⲭⲣⲏⲙⲁ",
    communication: "ⲡⲓⲙⲉⲧⲣⲉϥⲥⲁϫⲓ",
    reports: "ⲛⲓⲗⲟⲅⲟⲥ",
    security: "ⲡⲓⲧⲁϫⲣⲟ",
    welcome: "Ⲛⲟϥⲣⲓ ̀ⲉϩⲣⲏⲓ ̀ⲉϫⲱⲕ",
    activeRole: "Ⲧⲉⲝⲟⲩⲥⲓⲁ",
    totalMembers: "Ϣⲱⲡⲓ ̀ⲛⲓⲙⲉⲗⲟⲥ ⲧⲏⲣⲟⲩ",
    activeMembers: "Ⲛⲓⲙⲉⲗⲟⲥ ⲉⲧⲉⲛϩⲏⲧ",
    upcomingEvents: "Ⲛⲓϣⲁⲓ ̀ⲉⲑⲛⲏⲟⲩ",
    totalBudget: "Ⲡⲓⲭⲣⲏⲙⲁ ⲧⲏⲣϥ",
    searchPlaceholder: "Scanning ⲛⲓⲙⲉⲗⲟⲥ...",
    familyTree: "Ⲧⲫⲩⲗⲏ ̀ⲛⲧⲉ ϯⲉⲕⲕⲗⲏⲥⲓⲁ",
    prayerRequests: "Ⲧⲱⲃϩ ̀ⲛⲧⲉ ̀ⲡϫⲟⲓⲥ",
    donations: "Ⲡⲓⲧⲁⲓⲟ ̀ⲛⲭⲣⲏⲙⲁ",
    expenses: "ⲡⲓⲥⲱⲃⲉ ̀ⲛⲭⲣⲏⲙⲁ",
    auditLogs: "Ⲡⲓⲥϧⲁⲓ ̀ⲛⲧⲉ ⲛⲓϩⲃⲏⲟⲩⲓ",
    copticGreeting: "Ⲛⲟϥⲣⲓ ̀ⲉϩⲟⲟⲩ! (Good Day)"
  }
};

// ==========================================
// 3. INITIAL PRACTICAL DATABASE SEED DATA
// ==========================================

export const initialMembers: Member[] = [
  {
    id: 'm1',
    fullName: 'مينا سمير جرجس',
    fullNameEn: 'Mina Samir Girgis',
    age: 28,
    gender: 'ذكر',
    phone: '01223456789',
    email: 'mina.samir@example.com',
    address: 'شبرا، القاهرة',
    service: 'جامعي',
    status: 'خادم',
    avatar: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150',
    qrCode: 'KENISA-M1-MINA',
    familyId: 'fam-samir',
    familyRole: 'أب',
    joinDate: '2020-01-15',
    tags: ['Active', 'Leader']
  },
  {
    id: 'm2',
    fullName: 'مارينا وجيه نجيب',
    fullNameEn: 'Marina Wagih Naguib',
    age: 24,
    gender: 'أنثى',
    phone: '01004561234',
    email: 'marina.wagih@example.com',
    address: 'مصر الجديدة، القاهرة',
    service: 'جامعي',
    status: 'نشط',
    avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150',
    qrCode: 'KENISA-M2-MARINA',
    familyId: 'fam-wagih',
    familyRole: 'أم',
    joinDate: '2021-03-22',
    tags: ['Active', 'Newcomer']
  },
  {
    id: 'm3',
    fullName: 'أبانوب فايز عياد',
    fullNameEn: 'Abanoub Fayez Ayad',
    age: 17,
    gender: 'ذكر',
    phone: '01119876543',
    parentPhone: '01221122334',
    address: 'الزيتون، القاهرة',
    service: 'ثانوي',
    status: 'نشط',
    avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
    qrCode: 'KENISA-M3-ABANOUB',
    familyId: 'fam-samir',
    familyRole: 'ابن',
    joinDate: '2022-09-01',
    tags: ['Active']
  },
  {
    id: 'm4',
    fullName: 'دميانة كيرلس حبيب',
    fullNameEn: 'Demiana Kirollos Habib',
    age: 15,
    gender: 'أنثى',
    phone: '01556784321',
    parentPhone: '01009988776',
    address: 'شبرا، القاهرة',
    service: 'ثانوي',
    status: 'متردد',
    avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150',
    qrCode: 'KENISA-M4-DEMIANA',
    familyId: 'fam-wagih',
    familyRole: 'ابنة',
    joinDate: '2023-11-10',
    tags: ['Newcomer']
  },
  {
    id: 'm5',
    fullName: 'يوحنا عماد فخري',
    fullNameEn: 'Yohanna Emad Fakhry',
    age: 32,
    gender: 'ذكر',
    phone: '01201201201',
    email: 'yohanna.emad@example.com',
    address: 'المعادي، القاهرة',
    service: 'إعداد خدام',
    status: 'خادم',
    avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150',
    qrCode: 'KENISA-M5-YOHANNA',
    familyId: 'fam-fakhry',
    familyRole: 'أب',
    joinDate: '2018-05-18',
    tags: ['Leader']
  }
];

export const initialEvents: ChurchEvent[] = [
  {
    id: 'e1',
    title: 'القداس الإلهي الأسبوعي',
    titleEn: 'Weekly Divine Liturgy',
    date: '2026-07-03',
    time: '06:00 - 08:30 ص',
    location: 'الكنيسة الكبرى',
    description: 'القداس الإلهي الرئيسي ليوم الجمعة بحضور مجمع الآباء الموقرين.',
    rsvpCount: 240,
    expectedAttendance: 300,
    capacity: 400,
    resourceBooked: 'الكنيسة الكبرى'
  },
  {
    id: 'e2',
    title: 'اجتماع شباب ثانوي وجامعي',
    titleEn: 'Youth Meeting',
    date: '2026-07-03',
    time: '06:00 - 08:00 م',
    location: 'مسرح الكنيسة - الدور الثاني',
    description: 'اجتماع الشباب الأسبوعي تحت رعاية قدس أبونا يوحنا وموضوع روحي خاص بالخدمة.',
    rsvpCount: 85,
    expectedAttendance: 120,
    capacity: 150,
    resourceBooked: 'مسرح الكنيسة'
  }
];

export const initialExpenses: Expense[] = [
  {
    id: 'ex1',
    title: 'شراء كتب ومناهج مهرجان الكرازة',
    category: 'أنشطة',
    amount: 3500,
    date: '2026-06-25',
    recordedBy: 'أبانوب فايز',
    receiptNumber: 'REC-2026-102',
    notes: 'توزيع الكتب على فصول الطفولة وإعداد خدام'
  },
  {
    id: 'ex2',
    title: 'مساعدات شهرية للأسر المستورة (أخوة الرب)',
    category: 'مساعدات',
    amount: 25000,
    date: '2026-06-15',
    recordedBy: 'أبونا يوحنا',
    receiptNumber: 'REC-2026-085',
    notes: 'توزيع البركة الشهرية لدفعة يونيو'
  }
];

export const initialDonations: Donation[] = [
  {
    id: 'd1',
    donorName: 'فاعل خير',
    amount: 5000,
    category: 'تبرع عام',
    date: '2026-06-28',
    paymentMethod: 'نقدي',
    receiptNumber: 'DON-2026-451'
  },
  {
    id: 'd2',
    donorName: 'أ. سامح منير',
    amount: 1500,
    category: 'عشور',
    date: '2026-06-27',
    paymentMethod: 'محفظة إلكترونية',
    receiptNumber: 'DON-2026-452'
  }
];

export const initialPrayerRequests: PrayerRequest[] = [
  {
    id: 'p1',
    name: 'تاسوني مارينا وجيه',
    request: 'طلب صلاة لأجل شفاء مريض يتألم بشدة من مرض السرطان.',
    date: '2026-06-29',
    status: 'جديدة',
    supportersCount: 14,
    supportedBy: ['u1', 'u3']
  }
];

export const initialAnnouncements: Announcement[] = [
  {
    id: 'a1',
    title: 'تنويه هام بشأن مواعيد قداسات صوم الرسل',
    content: 'نود إحاطة شعب الكنيسة المبارك علماً بأن قداسات صوم الرسل ستبدأ من الساعة 7:00 ص وحتى 9:30 ص أيام الاثنين والأربعاء والجمعة.',
    date: '2026-06-29',
    pinned: true,
    author: 'أبونا يوحنا',
    category: 'عام'
  }
];

export const initialMessages: ChatMessage[] = [
  {
    id: 'msg1',
    senderName: 'أبونا يوحنا عماد',
    senderRole: 'كاهن الكنيسة',
    senderAvatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150',
    content: 'سلام ونعمة يا أحبائي الخدام والتابعين. كيف هي استعداداتكم لمهرجان الكرازة؟',
    timestamp: '10:15 ص',
    pinned: true
  }
];

export const initialLogs: AuditLog[] = [
  {
    id: 'l1',
    userId: 'u1',
    userName: 'مينا سمير',
    action: 'تسجيل الحضور',
    details: 'تم تسجيل حضور اجتماع الشباب ليوم الجمعة 26-06-2026',
    timestamp: '2026-06-26 20:15:30'
  }
];

export const initialBookings: ResourceBooking[] = [
  {
    id: 'b1',
    resourceName: 'القاعة الكبرى',
    bookedBy: 'تاسوني مارينا',
    date: '2026-07-03',
    timeSlot: '09:00 ص - 11:00 ص',
    status: 'مؤكد'
  }
];


// ==========================================
// 4. SUBCOMPONENT: DASHBOARD
// ==========================================

interface DashboardProps {
  members: Member[];
  events: ChurchEvent[];
  expenses: Expense[];
  donations: Donation[];
  logs: AuditLog[];
  onNavigate: (tab: string) => void;
  userRole: string;
}

export function DashboardComponent({ members, events, expenses, donations, logs, onNavigate, userRole }: DashboardProps) {
  const totalMembers = members.length;
  const activeMembers = members.filter(m => m.status === 'نشط' || m.status === 'خادم').length;
  const totalBudget = donations.reduce((sum, d) => sum + d.amount, 0) - expenses.reduce((sum, e) => sum + e.amount, 0);
  const totalEvents = events.length;

  const monthlyChartData = [
    { name: 'يناير', تبرعات: 15000, مصروفات: 8000, حضور: 120 },
    { name: 'فبراير', تبرعات: 18000, مصروفات: 12000, حضور: 140 },
    { name: 'مارس', تبرعات: 24000, مصروفات: 10000, حضور: 165 },
    { name: 'أبريل', تبرعات: 21000, مصروفات: 15000, حضور: 155 },
    { name: 'مايو', تبرعات: 30000, مصروفات: 9000, حضور: 190 },
    { name: 'يونيو', تبرعات: 38000, مصروفات: 22000, حضور: 210 },
  ];

  const recentMembers = [...members].reverse().slice(0, 4);
  const recentLogs = [...logs].reverse().slice(0, 5);

  return (
    <div className="space-y-6 text-right">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div onClick={() => onNavigate('members')} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 flex items-center justify-between cursor-pointer hover:shadow-md transition-all">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400">إجمالي الأعضاء المسجلين</span>
            <h3 className="text-3xl font-bold text-slate-800 dark:text-slate-100">{totalMembers}</h3>
            <span className="text-xs text-green-500 bg-green-50 dark:bg-green-950/30 px-2 py-0.5 rounded-full">{activeMembers} نشط</span>
          </div>
          <div className="p-3.5 rounded-xl bg-blue-50 dark:bg-blue-950/30 text-blue-600">
            <Users className="w-6 h-6" />
          </div>
        </div>

        {/* Card 2 */}
        <div onClick={() => onNavigate('events')} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 flex items-center justify-between cursor-pointer hover:shadow-md transition-all">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400">الفعاليات الحالية والقداسات</span>
            <h3 className="text-3xl font-bold text-slate-800 dark:text-slate-100">{totalEvents}</h3>
            <span className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-950/30 px-2 py-0.5 rounded-full">محدث هذا الأسبوع</span>
          </div>
          <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 text-amber-600">
            <CalendarRange className="w-6 h-6" />
          </div>
        </div>

        {/* Card 3 */}
        <div onClick={() => onNavigate('finance')} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 flex items-center justify-between cursor-pointer hover:shadow-md transition-all">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400">رصيد الصندوق والميزانية</span>
            <h3 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{totalBudget.toLocaleString()} ج.م</h3>
            <span className="text-xs text-emerald-500 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-0.5 rounded-full">الحساب متزن</span>
          </div>
          <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600">
            <DollarSign className="w-6 h-6" />
          </div>
        </div>

        {/* Card 4 */}
        <div onClick={() => onNavigate('reports')} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 flex items-center justify-between cursor-pointer hover:shadow-md transition-all">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400">نسبة حضور الاجتماعات</span>
            <h3 className="text-3xl font-bold text-slate-800 dark:text-slate-100">84.5%</h3>
            <span className="text-xs text-blue-500 bg-blue-50 dark:bg-blue-950/30 px-2 py-0.5 rounded-full">استقرار في الحضور</span>
          </div>
          <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600">
            <UserCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <span>مخطط الحضور والتدفقات المالية للعام الحالي</span>
          </h4>
          <div className="h-72 w-full text-xs">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monthlyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDonations" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorAttendance" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Legend iconType="circle" />
                <Area type="monotone" dataKey="تبرعات" stroke="#10b981" fillOpacity={1} fill="url(#colorDonations)" strokeWidth={2} name="التبرعات والعطاء (ج.م)" />
                <Area type="monotone" dataKey="حضور" stroke="#3b82f6" fillOpacity={1} fill="url(#colorAttendance)" strokeWidth={2} name="متوسط حضور الشعب" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 space-y-4 flex flex-col justify-between">
          <div>
            <h4 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center gap-2 mb-4">
              <CalendarRange className="w-5 h-5 text-amber-500" />
              <span>الفعاليات والخدمات القادمة</span>
            </h4>
            <div className="space-y-3">
              {events.map((ev) => (
                <div key={ev.id} className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex flex-col gap-2 relative overflow-hidden">
                  <div className="absolute right-0 top-0 bottom-0 w-1 bg-amber-500"></div>
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-100 text-sm">{ev.title}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-mono">{ev.time}</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{ev.description}</p>
                </div>
              ))}
            </div>
          </div>
          <button onClick={() => onNavigate('events')} className="w-full py-2.5 px-4 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-amber-500 text-slate-700 dark:text-slate-300 text-xs font-semibold hover:text-amber-600 transition-all flex items-center justify-center gap-1.5 cursor-pointer mt-4">
            <span>عرض وحجز كل القاعات والفعاليات</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-500" />
            <span>سجل العمليات والأنشطة الإدارية</span>
          </h4>
          <div className="flow-root">
            <ul className="-mb-8">
              {recentLogs.map((log, logIdx) => (
                <li key={log.id}>
                  <div className="relative pb-8">
                    {logIdx !== recentLogs.length - 1 ? (
                      <span className="absolute top-4 right-4 -ml-px h-full w-0.5 bg-slate-200 dark:bg-slate-700" aria-hidden="true" />
                    ) : null}
                    <div className="relative flex space-x-3 space-x-reverse text-right">
                      <div>
                        <span className="h-8 w-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center ring-8 ring-white">
                          <Info className="w-4 h-4 text-amber-500" />
                        </span>
                      </div>
                      <div className="flex-1 min-w-0 pr-3.5">
                        <div className="text-xs text-slate-500 flex items-center justify-between">
                          <span className="font-bold text-slate-800 dark:text-slate-200">{log.userName}</span>
                          <span className="text-[10px] font-mono">{log.timestamp}</span>
                        </div>
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mt-1">{log.action}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{log.details}</p>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center gap-2">
            <Star className="w-5 h-5 text-amber-400 fill-current" />
            <span>الأعضاء المضافين حديثاً</span>
          </h4>
          <div className="space-y-3">
            {recentMembers.map(member => (
              <div key={member.id} className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                <img src={member.avatar} alt={member.fullName} className="w-10 h-10 rounded-full object-cover border border-amber-400/40" />
                <div className="flex-1 min-w-0 text-right">
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{member.fullName}</p>
                  <p className="text-xs text-slate-400 truncate">{member.service} • {member.address}</p>
                </div>
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">{member.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 5. SUBCOMPONENT: MEMBERS MANAGEMENT
// ==========================================

interface MembersProps {
  members: Member[];
  onAddMember: (member: Member) => void;
  onUpdateMember: (id: string, updates: Partial<Member>) => void;
  onDeleteMember: (id: string) => void;
  onBulkMessage: (ids: string[], msg: string) => void;
}

export function MembersComponent({ members, onAddMember, onUpdateMember, onDeleteMember, onBulkMessage }: MembersProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGender, setSelectedGender] = useState<string>('الكل');
  const [selectedStatus, setSelectedStatus] = useState<string>('الكل');
  const [selectedService, setSelectedService] = useState<string>('الكل');
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [service, setService] = useState('جامعي');
  const [status, setStatus] = useState<'نشط' | 'غير نشط' | 'متردد' | 'خادم'>('نشط');

  const filteredMembers = members.filter(member => {
    const matchesSearch = member.fullName.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          member.phone.includes(searchQuery);
    const matchesGender = selectedGender === 'الكل' || member.gender === selectedGender;
    const matchesStatus = selectedStatus === 'الكل' || member.status === selectedStatus;
    const matchesService = selectedService === 'الكل' || member.service === selectedService;
    return matchesSearch && matchesGender && matchesStatus && matchesService;
  });

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !phone) return;

    onAddMember({
      id: 'm-' + Date.now(),
      fullName,
      age: 20,
      gender: 'ذكر',
      phone,
      address,
      service,
      status,
      avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150',
      qrCode: 'KENISA-' + Date.now(),
      familyId: 'fam-samir',
      familyRole: 'ابن',
      joinDate: new Date().toISOString().split('T')[0],
      tags: ['Active']
    });

    setIsAdding(false);
    setFullName('');
    setPhone('');
    setAddress('');
  };

  return (
    <div className="space-y-6 text-right">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white dark:bg-[#1a2332] p-4 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <div>
          <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg">بوابة إدارة الأعضاء الكنسيين</h3>
          <p className="text-xs text-slate-500 mt-1">تصفية وبحث متطور، إدخال بيانات الأعضاء ومتابعة الخدمات</p>
        </div>
        <button onClick={() => setIsAdding(!isAdding)} className="px-4 py-2 text-xs font-semibold bg-gradient-to-r from-[#1a365d] to-[#2a4365] text-white rounded-xl flex items-center gap-1.5 cursor-pointer">
          <Plus className="w-4 h-4" />
          <span>إضافة عضو جديد</span>
        </button>
      </div>

      {isAdding && (
        <form onSubmit={handleRegisterSubmit} className="bg-white dark:bg-[#1a2332] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base border-b pb-3">تسجيل عضو كنسي جديد</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="الاسم ثلاثي أو رباعي..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="text" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="رقم الموبايل..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="text" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="العنوان بالتفصيل..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <select value={service} onChange={(e) => setService(e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl">
              <option value="جامعي">جامعي</option>
              <option value="ثانوي">ثانوي</option>
              <option value="أطفال">أطفال</option>
              <option value="إعداد خدام">إعداد خدام</option>
            </select>
          </div>
          <button type="submit" className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold">حفظ العضو الجديد</button>
        </form>
      )}

      {/* Filter and table */}
      <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1 relative">
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="البحث باسم العضو أو الهاتف..." className="w-full bg-slate-50 dark:bg-slate-800 border px-3 py-2 pr-10 text-xs rounded-xl" />
            <Search className="absolute right-3 top-2.5 w-4.5 h-4.5 text-slate-400" />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b text-slate-400 font-bold">
                <th className="py-2 px-3 text-right">الاسم</th>
                <th className="py-2 px-3 text-right">الموبايل</th>
                <th className="py-2 px-3 text-right">العنوان</th>
                <th className="py-2 px-3 text-right">المرحلة / الخدمة</th>
                <th className="py-2 px-3 text-right">الحالة الكنسية</th>
                <th className="py-2 px-3 text-center">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              {filteredMembers.map(m => (
                <tr key={m.id} className="border-b hover:bg-slate-50/50">
                  <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-100">{m.fullName}</td>
                  <td className="py-3 px-3 font-mono">{m.phone}</td>
                  <td className="py-3 px-3 text-slate-500">{m.address}</td>
                  <td className="py-3 px-3">{m.service}</td>
                  <td className="py-3 px-3">
                    <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">{m.status}</span>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <button onClick={() => onDeleteMember(m.id)} className="p-1 text-rose-500 hover:bg-rose-50 rounded-lg">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 6. SUBCOMPONENT: EVENTS & ROOM BOOKINGS
// ==========================================

interface EventsProps {
  events: ChurchEvent[];
  bookings: ResourceBooking[];
  onAddEvent: (event: ChurchEvent) => void;
  onAddBooking: (booking: ResourceBooking) => void;
  onRSVP: (eventId: string) => void;
}

export function EventsComponent({ events, bookings, onAddEvent, onAddBooking, onRSVP }: EventsProps) {
  const [isAddingEvent, setIsAddingEvent] = useState(false);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [location, setLocation] = useState('الكنيسة الكبرى');
  const [description, setDescription] = useState('');

  const handleCreateEvent = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !date) return;

    onAddEvent({
      id: 'e-' + Date.now(),
      title,
      date,
      time,
      location,
      description,
      rsvpCount: 0,
      expectedAttendance: 100,
      capacity: 150
    });

    setIsAddingEvent(false);
    setTitle('');
    setDate('');
    setTime('');
    setDescription('');
  };

  return (
    <div className="space-y-6 text-right">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white dark:bg-[#1a2332] p-4 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <div>
          <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg">القداسات، الخدمات والاجتماعات الكنسية</h3>
          <p className="text-xs text-slate-500 mt-1">جدولة الصلوات، الخدمات الطقسية وتجنب تضارب الحجوزات</p>
        </div>
        <button onClick={() => setIsAddingEvent(!isAddingEvent)} className="px-4 py-2 text-xs font-semibold bg-[#1a365d] hover:bg-opacity-90 text-white rounded-xl flex items-center gap-1.5 cursor-pointer">
          <Plus className="w-4 h-4" />
          <span>إضافة حدث / قداس جديد</span>
        </button>
      </div>

      {isAddingEvent && (
        <form onSubmit={handleCreateEvent} className="bg-white dark:bg-[#1a2332] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base border-b pb-2">جدولة مناسبة أو قداس إلهي جديد</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input type="text" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="اسم المناسبة / القداس الإلهي..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="text" required value={time} onChange={(e) => setTime(e.target.value)} placeholder="الموعد (مثلاً: 06:00 ص - 08:30 ص)" className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="text" required value={location} onChange={(e) => setLocation(e.target.value)} placeholder="المكان (مثلاً: الكنيسة الكبرى)" className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="تفاصيل الخدمة أو الآباء الحاضرين..." className="w-full md:col-span-2 bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
          </div>
          <button type="submit" className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold">تأكيد الجدولة والنشاط</button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base mb-3">الصلوات والمناسبات المجدولة</h4>
          <div className="space-y-3">
            {events.map(ev => (
              <div key={ev.id} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm relative overflow-hidden">
                <div className="absolute right-0 top-0 bottom-0 w-1 bg-amber-500"></div>
                <div className="flex justify-between items-center">
                  <h5 className="font-bold text-slate-800 dark:text-slate-100 text-sm">{ev.title}</h5>
                  <span className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-950/20 px-2.5 py-0.5 rounded-full font-bold">{ev.date}</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">{ev.description}</p>
                <div className="mt-3 pt-3 border-t flex justify-between items-center text-xs text-slate-400">
                  <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {ev.location}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {ev.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base mb-3">حجوزات القاعات والبروجيكتور والموارد الكنسية</h4>
          <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
            <div className="space-y-3">
              {bookings.map(bk => (
                <div key={bk.id} className="flex justify-between items-center p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border text-xs">
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 font-bold rounded-full">{bk.status}</span>
                  <div className="text-right">
                    <p className="font-bold text-slate-800 dark:text-slate-100">{bk.resourceName}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">الحاجز: {bk.bookedBy} • التاريخ: {bk.date} ({bk.timeSlot})</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 7. SUBCOMPONENT: FINANCE LEDGER
// ==========================================

interface FinanceProps {
  expenses: Expense[];
  donations: Donation[];
  onAddExpense: (expense: Expense) => void;
  onAddDonation: (donation: Donation) => void;
}

export function FinanceComponent({ expenses, donations, onAddExpense, onAddDonation }: FinanceProps) {
  const [isAddingExpense, setIsAddingExpense] = useState(false);
  const [isAddingDonation, setIsAddingDonation] = useState(false);

  const [donorName, setDonorName] = useState('');
  const [donationAmount, setDonationAmount] = useState<number>(0);
  const [donationCategory, setDonationCategory] = useState<'عشور' | 'بكور' | 'تبرع عام' | 'إخوة الرب'>('عشور');

  const [expenseTitle, setExpenseTitle] = useState('');
  const [expenseAmount, setExpenseAmount] = useState<number>(0);
  const [expenseCategory, setExpenseCategory] = useState<'صيانة' | 'مساعدات' | 'أنشطة' | 'أجور' | 'أخرى'>('أنشطة');

  const totalDonations = donations.reduce((sum, d) => sum + d.amount, 0);
  const totalExpenses = expenses.reduce((sum, e) => sum + e.amount, 0);
  const balance = totalDonations - totalExpenses;

  const handleDonationSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!donationAmount) return;

    onAddDonation({
      id: 'd-' + Date.now(),
      donorName: donorName || 'فاعل خير',
      amount: donationAmount,
      category: donationCategory,
      date: new Date().toISOString().split('T')[0],
      paymentMethod: 'نقدي',
      receiptNumber: 'DON-' + Date.now().toString().slice(-4)
    });

    setIsAddingDonation(false);
    setDonorName('');
    setDonationAmount(0);
  };

  const handleExpenseSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!expenseAmount || !expenseTitle) return;

    onAddExpense({
      id: 'ex-' + Date.now(),
      title: expenseTitle,
      category: expenseCategory,
      amount: expenseAmount,
      date: new Date().toISOString().split('T')[0],
      recordedBy: 'الخادم المسؤول',
      receiptNumber: 'REC-' + Date.now().toString().slice(-4)
    });

    setIsAddingExpense(false);
    setExpenseTitle('');
    setExpenseAmount(0);
  };

  return (
    <div className="space-y-6 text-right">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 text-right space-y-1.5">
          <span className="text-xs font-semibold text-slate-400">إجمالي العطايا والتبرعات</span>
          <h3 className="text-2xl font-bold text-emerald-500 font-mono">+{totalDonations.toLocaleString()} ج.م</h3>
        </div>
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 text-right space-y-1.5">
          <span className="text-xs font-semibold text-slate-400">إجمالي المصروفات والمساعدات</span>
          <h3 className="text-2xl font-bold text-rose-500 font-mono">-{totalExpenses.toLocaleString()} ج.م</h3>
        </div>
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 text-right space-y-1.5">
          <span className="text-xs font-semibold text-slate-400">الرصيد المتاح بالصندوق الكنسي</span>
          <h3 className="text-2xl font-bold text-blue-500 font-mono">{balance.toLocaleString()} ج.م</h3>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={() => setIsAddingDonation(!isAddingDonation)} className="px-4 py-2 text-xs font-bold bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 transition-colors">تسجيل تبرع / عطاء</button>
        <button onClick={() => setIsAddingExpense(!isAddingExpense)} className="px-4 py-2 text-xs font-bold bg-rose-500 text-white rounded-xl hover:bg-rose-600 transition-colors">تسجيل مستند صرف / مصروف</button>
      </div>

      {isAddingDonation && (
        <form onSubmit={handleDonationSubmit} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2">تسجيل إيصال تبرع جديد</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input type="text" value={donorName} onChange={(e) => setDonorName(e.target.value)} placeholder="اسم المتبرع (اتركه فارغاً لفاعل خير)..." className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="number" required value={donationAmount || ''} onChange={(e) => setDonationAmount(Number(e.target.value))} placeholder="قيمة العطاء (ج.م)..." className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <select value={donationCategory} onChange={(e) => setDonationCategory(e.target.value as any)} className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl">
              <option value="عشور">عشور</option>
              <option value="بكور">بكور</option>
              <option value="تبرع عام">تبرع عام</option>
              <option value="إخوة الرب">إخوة الرب</option>
            </select>
          </div>
          <button type="submit" className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold">حفظ إيصال التبرع</button>
        </form>
      )}

      {isAddingExpense && (
        <form onSubmit={handleExpenseSubmit} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2">تسجيل إيصال صرف جديد</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input type="text" required value={expenseTitle} onChange={(e) => setExpenseTitle(e.target.value)} placeholder="بيان الصرف / الغرض..." className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <input type="number" required value={expenseAmount || ''} onChange={(e) => setExpenseAmount(Number(e.target.value))} placeholder="المبلغ المصروف (ج.م)..." className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
            <select value={expenseCategory} onChange={(e) => setExpenseCategory(e.target.value as any)} className="bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl">
              <option value="صيانة">صيانة</option>
              <option value="مساعدات">مساعدات (أخوة الرب)</option>
              <option value="أنشطة">أنشطة كنسية</option>
              <option value="أجور">أجور ومرتبات</option>
              <option value="أخرى">أخرى</option>
            </select>
          </div>
          <button type="submit" className="px-5 py-2 bg-rose-500 hover:bg-rose-600 text-white rounded-xl text-xs font-bold">حفظ إيصال الصرف</button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base">سجل المقبوضات والعطايا</h4>
          <div className="space-y-2">
            {donations.map(dn => (
              <div key={dn.id} className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border flex justify-between items-center text-xs">
                <span className="font-bold text-emerald-500">+{dn.amount} ج.م</span>
                <div className="text-right">
                  <p className="font-bold">{dn.donorName}</p>
                  <p className="text-[10px] text-slate-400">{dn.category} • {dn.date} • إيصال {dn.receiptNumber}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base">سجل المصروفات والمدفوعات</h4>
          <div className="space-y-2">
            {expenses.map(ex => (
              <div key={ex.id} className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border flex justify-between items-center text-xs">
                <span className="font-bold text-rose-500">-{ex.amount} ج.م</span>
                <div className="text-right">
                  <p className="font-bold">{ex.title}</p>
                  <p className="text-[10px] text-slate-400">{ex.category} • {ex.date} • إيصال {ex.receiptNumber}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 8. SUBCOMPONENT: INTERNAL COMMUNICATION
// ==========================================

interface CommunicationProps {
  announcements: Announcement[];
  prayerRequests: PrayerRequest[];
  chatMessages: ChatMessage[];
  onAddAnnouncement: (ann: Announcement) => void;
  onAddPrayerRequest: (req: PrayerRequest) => void;
  onAddChatMessage: (msg: ChatMessage) => void;
  onSupportPrayer: (prayerId: string) => void;
}

export function CommunicationComponent({
  announcements,
  prayerRequests,
  chatMessages,
  onAddAnnouncement,
  onAddPrayerRequest,
  onAddChatMessage,
  onSupportPrayer
}: CommunicationProps) {
  const [chatInput, setChatInput] = useState('');
  const [isAddingAnn, setIsAddingAnn] = useState(false);
  const [annTitle, setAnnTitle] = useState('');
  const [annContent, setAnnContent] = useState('');

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    onAddChatMessage({
      id: 'msg-' + Date.now(),
      senderName: 'الخادم مينا سمير',
      senderRole: 'أمين الخدمة',
      senderAvatar: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150',
      content: chatInput,
      timestamp: new Date().toLocaleTimeString('ar-EG', { hour: 'numeric', minute: '2-digit' })
    });

    setChatInput('');
  };

  const handlePostAnnouncement = (e: React.FormEvent) => {
    e.preventDefault();
    if (!annTitle || !annContent) return;

    onAddAnnouncement({
      id: 'a-' + Date.now(),
      title: annTitle,
      content: annContent,
      date: new Date().toISOString().split('T')[0],
      pinned: false,
      author: 'الخادم مينا سمير',
      category: 'عام'
    });

    setIsAddingAnn(false);
    setAnnTitle('');
    setAnnContent('');
  };

  return (
    <div className="space-y-6 text-right">
      <div className="flex justify-between items-center bg-white dark:bg-[#1a2332] p-4 rounded-2xl border shadow-sm">
        <div>
          <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg">بوابة التواصل والخدمة الداخلي</h3>
          <p className="text-xs text-slate-500">نشر التنويهات، تبادل طلبات الصلاة والمباركة، والمحادثة التفاعلية للخدام</p>
        </div>
        <button onClick={() => setIsAddingAnn(!isAddingAnn)} className="px-4 py-2 text-xs font-semibold bg-indigo-500 text-white rounded-xl hover:bg-indigo-600 transition-colors">نشر تعميم كنسي هام</button>
      </div>

      {isAddingAnn && (
        <form onSubmit={handlePostAnnouncement} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2">نشر تعميم أو تنويه لشعب الكنيسة</h4>
          <input type="text" required value={annTitle} onChange={(e) => setAnnTitle(e.target.value)} placeholder="عنوان التنبيه..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
          <textarea required value={annContent} onChange={(e) => setAnnContent(e.target.value)} placeholder="محتوى التنبيه والتعليمات..." className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-sm rounded-xl" />
          <button type="submit" className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold">نشر الآن في اللوحة العامة</button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Announcements List */}
        <div className="lg:col-span-2 space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base">التعميمات واللوحة الإخبارية</h4>
          <div className="space-y-3">
            {announcements.map(ann => (
              <div key={ann.id} className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm relative">
                <div className="absolute right-0 top-0 bottom-0 w-1 bg-indigo-500"></div>
                <h5 className="font-bold text-slate-800 dark:text-slate-100 text-sm">{ann.title}</h5>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">{ann.content}</p>
                <div className="mt-3 text-[10px] text-slate-400">الناشر: {ann.author} • التاريخ: {ann.date}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Chat for Servants */}
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm flex flex-col justify-between h-[450px]">
          <div>
            <h4 className="font-bold text-slate-800 dark:text-slate-100 text-base border-b pb-2 flex items-center justify-end gap-1.5 mb-3">
              <span>دردشة الخدمة التفاعلية</span>
              <MessageSquare className="w-4 h-4 text-amber-500" />
            </h4>
            <div className="space-y-3.5 overflow-y-auto h-[280px] px-1">
              {chatMessages.map(msg => (
                <div key={msg.id} className="flex gap-2.5 items-start">
                  <img src={msg.senderAvatar} alt={msg.senderName} className="w-8 h-8 rounded-full object-cover" />
                  <div className="flex-1 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-2xl text-xs">
                    <div className="flex justify-between items-center text-[10px] text-slate-400 mb-1">
                      <span className="font-mono">{msg.timestamp}</span>
                      <span className="font-bold text-slate-700 dark:text-slate-300">{msg.senderName} ({msg.senderRole})</span>
                    </div>
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed text-right">{msg.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <form onSubmit={handleSendChat} className="mt-3 flex gap-2">
            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="اكتب رسالتك الخدمية هنا..." className="flex-1 bg-slate-50 dark:bg-slate-800 border px-3 py-2 text-xs rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500" />
            <button type="submit" className="p-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl transition-colors"><Send className="w-4 h-4" /></button>
          </form>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 9. SUBCOMPONENT: REPORTS & ANALYTICS
// ==========================================

interface ReportsProps {
  members: Member[];
  events: ChurchEvent[];
  expenses: Expense[];
  donations: Donation[];
}

export function ReportsComponent({ members, events, expenses, donations }: ReportsProps) {
  const [selectedService, setSelectedService] = useState<string>('الكل');
  const [reportResult, setReportResult] = useState<Member[]>([]);
  const [reportBuilt, setReportBuilt] = useState(false);

  const handleBuildReport = () => {
    const results = members.filter(member => {
      return selectedService === 'الكل' || member.service === selectedService;
    });
    setReportResult(results);
    setReportBuilt(true);
  };

  return (
    <div className="space-y-6 text-right">
      <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm text-right space-y-2">
        <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center justify-end gap-2">
          <span>مولد التقارير الكنسية والإحصائيات</span>
          <BarChart3 className="w-6 h-6 text-indigo-500" />
        </h3>
        <p className="text-xs text-slate-500">اختر الفلتر المناسب لتوليد تقارير كنسية مفصلة وطباعتها بضغطة زر واحدة</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2">تخصيص بنود البحث والتصفية</h4>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">تصفية الخدمة والمرحلة الدراسية</label>
              <select value={selectedService} onChange={(e) => setSelectedService(e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border p-2 text-xs rounded-xl focus:outline-none">
                <option value="الكل">الكل</option>
                <option value="جامعي">جامعي</option>
                <option value="ثانوي">ثانوي</option>
                <option value="أطفال">أطفال</option>
                <option value="إعداد خدام">إعداد خدام</option>
              </select>
            </div>
            <button onClick={handleBuildReport} className="w-full py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-xs font-bold transition-all">توليد التقرير الآن</button>
          </div>
        </div>

        <div className="lg:col-span-2 bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2">النتائج والتقارير المستخلصة</h4>
          {reportBuilt ? (
            <div className="space-y-3">
              <p className="text-xs text-slate-500">تم العثور على {reportResult.length} عضو كنسي مطابق للشروط.</p>
              <div className="max-h-64 overflow-y-auto space-y-2">
                {reportResult.map(r => (
                  <div key={r.id} className="p-2.5 bg-slate-50 dark:bg-slate-800/40 rounded-xl border flex justify-between items-center text-xs">
                    <span className="text-slate-400">{r.phone}</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-100">{r.fullName} ({r.service})</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400">قم بتحديد الشروط واضغط على توليد التقرير لعرض النتائج هنا.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 10. SUBCOMPONENT: SECURITY & RBAC
// ==========================================

interface SecurityProps {
  logs: AuditLog[];
  userRole: string;
}

export function SecurityComponent({ logs, userRole }: SecurityProps) {
  const sessions = [
    { id: 's1', device: 'Chrome / MacOS (جهاز كمبيوتر)', location: 'القاهرة، مصر', status: 'نشط حالياً' },
    { id: 's2', device: 'Safari / iPhone 14 (موبايل)', location: 'الجيزة، مصر', status: 'منذ ساعتين' },
  ];

  return (
    <div className="space-y-6 text-right">
      <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm text-right space-y-2">
        <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center justify-end gap-1.5">
          <span>الأمان والصلاحيات والتحكم الإداري</span>
          <ShieldAlert className="w-5 h-5 text-emerald-500" />
        </h3>
        <p className="text-xs text-slate-500">تتبع جميع العمليات وتعديلات الخدام وتحديد صلاحيات الوصول للنظام الكنسي</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm space-y-4">
            <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2 flex items-center justify-end gap-2">
              <span>سجل العمليات والأنشطة الإدارية</span>
              <Activity className="w-5 h-5 text-indigo-500" />
            </h4>
            <div className="overflow-x-auto text-xs">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b text-slate-400 font-bold">
                    <th className="py-2.5 px-3 text-right">الخادم</th>
                    <th className="py-2.5 px-3 text-right">العملية الإدارية</th>
                    <th className="py-2.5 px-3 text-right">التفاصيل الكنسية</th>
                    <th className="py-2.5 px-3 text-right">التاريخ والوقت</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} className="border-b hover:bg-slate-50/50">
                      <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-100">{log.userName}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 font-bold">{log.action}</span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-500">{log.details}</td>
                      <td className="py-2.5 px-3 font-mono">{log.timestamp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-[#1a2332] p-5 rounded-2xl border shadow-sm space-y-4">
          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm border-b pb-2 flex items-center justify-end gap-2">
            <span>الأجهزة والجلسات النشطة حالياً</span>
            <Users className="w-5 h-5 text-blue-600" />
          </h4>
          <div className="space-y-3">
            {sessions.map(sess => (
              <div key={sess.id} className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/30 border flex justify-between items-center text-xs">
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">{sess.status}</span>
                <div className="text-right">
                  <p className="font-bold text-slate-800 dark:text-slate-100">{sess.device}</p>
                  <p className="text-[10px] text-slate-400">{sess.location}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


// ==========================================
// 11. MAIN ENTRY APP COMPONENT
// ==========================================

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [lang, setLanguage] = useState<Language>('ar');
  const t = translations[lang];

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('dashboard');

  const [members, setMembers] = useState<Member[]>(initialMembers);
  const [events, setEvents] = useState<ChurchEvent[]>(initialEvents);
  const [expenses, setExpenses] = useState<Expense[]>(initialExpenses);
  const [donations, setDonations] = useState<Donation[]>(initialDonations);
  const [prayerRequests, setPrayerRequests] = useState<PrayerRequest[]>(initialPrayerRequests);
  const [announcements, setAnnouncements] = useState<Announcement[]>(initialAnnouncements);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(initialMessages);
  const [logs, setLogs] = useState<AuditLog[]>(initialLogs);
  const [bookings, setBookings] = useState<ResourceBooking[]>(initialBookings);

  const [currentUser] = useState({
    id: 'u1',
    name: 'الخادم مينا سمير',
    role: 'Admin' as 'Admin' | 'Father' | 'Servant' | 'Visitor',
    avatar: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150',
    email: 'mina.samir@example.com',
    phone: '01223456789'
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  const pushAuditLog = (action: string, details: string) => {
    const newLog: AuditLog = {
      id: 'log-' + Date.now(),
      userId: currentUser.id,
      userName: currentUser.name,
      action,
      details,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19)
    };
    setLogs(prev => [newLog, ...prev]);
  };

  const handleAddMember = (newMember: Member) => {
    setMembers(prev => [...prev, newMember]);
    pushAuditLog('إضافة عضو كنسي', `تم تسجيل العضو ${newMember.fullName} بنجاح.`);
  };

  const handleUpdateMember = (id: string, updates: Partial<Member>) => {
    setMembers(prev => prev.map(m => m.id === id ? { ...m, ...updates } : m));
    pushAuditLog('تحديث بيانات عضو', `تحديث بيانات العضو ذو المعرف ${id}.`);
  };

  const handleDeleteMember = (id: string) => {
    setMembers(prev => prev.filter(m => m.id !== id));
    pushAuditLog('حذف عضو', `تم حذف العضو ذو المعرف ${id}.`);
  };

  const handleAddEvent = (newEvent: ChurchEvent) => {
    setEvents(prev => [...prev, newEvent]);
    pushAuditLog('إضافة مناسبة / قداس', `تمت جدولة ${newEvent.title} بنجاح.`);
  };

  const handleAddBooking = (newBooking: ResourceBooking) => {
    setBookings(prev => [...prev, newBooking]);
    pushAuditLog('حجز مورد كنسي', `تم تأكيد حجز ${newBooking.resourceName}.`);
  };

  const handleAddExpense = (newExpense: Expense) => {
    setExpenses(prev => [...prev, newExpense]);
    pushAuditLog('إضافة مصروفات', `صرف مبلغ ${newExpense.amount} ج.م في بند ${newExpense.title}.`);
  };

  const handleAddDonation = (newDonation: Donation) => {
    setDonations(prev => [...prev, newDonation]);
    pushAuditLog('تسجيل تبرع / عطاء', `استلام مبلغ ${newDonation.amount} ج.م من ${newDonation.donorName}.`);
  };

  const handleAddAnnouncement = (newAnn: Announcement) => {
    setAnnouncements(prev => [newAnn, ...prev]);
    pushAuditLog('نشر تعميم كنسي', `تم نشر تعميم بعنوان ${newAnn.title}.`);
  };

  const handleAddChatMessage = (newMsg: ChatMessage) => {
    setChatMessages(prev => [...prev, newMsg]);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0f172a] text-slate-800 dark:text-slate-100 flex flex-col font-sans transition-colors duration-300">
      <header className="bg-slate-900 text-white px-4 md:px-6 py-4 flex items-center justify-between shadow-md border-b border-slate-800 z-50">
        <div className="flex items-center gap-3">
          <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer">
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="text-right">
            <h1 className="font-bold text-sm tracking-wide">{t.title}</h1>
            <p className="text-[10px] text-slate-300 hidden md:block">{t.subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 bg-slate-800/40 px-2 py-1 rounded-xl border border-slate-700">
            <Globe className="w-4 h-4 text-amber-400" />
            <select value={lang} onChange={(e) => setLanguage(e.target.value as Language)} className="bg-transparent text-xs text-slate-200 focus:outline-none font-semibold cursor-pointer">
              <option value="ar" className="text-slate-800">العربية</option>
              <option value="en" className="text-slate-800">English</option>
              <option value="cop" className="text-slate-800">Ϯⲁⲥⲡⲓ</option>
            </select>
          </div>

          <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} className="p-1.5 rounded-xl bg-slate-800/40 border border-slate-700 text-slate-200 transition-colors cursor-pointer">
            {theme === 'light' ? <Moon className="w-4.5 h-4.5" /> : <Sun className="w-4.5 h-4.5 text-amber-400" />}
          </button>
        </div>
      </header>

      <div className="flex-1 flex relative overflow-hidden">
        <aside className={`bg-slate-900 text-slate-300 border-l border-slate-800 flex flex-col justify-between transition-all duration-300 absolute md:relative top-0 bottom-0 right-0 z-40 ${isSidebarOpen ? 'w-64 translate-x-0' : 'w-0 translate-x-64 md:w-0'}`}>
          <div className="p-4 space-y-5 overflow-y-auto flex-1 text-right">
            <div className="p-3 bg-slate-800/40 rounded-2xl border flex items-center gap-3 relative overflow-hidden">
              <div className="absolute right-0 top-0 bottom-0 w-1 bg-amber-500"></div>
              <img src={currentUser.avatar} alt={currentUser.name} className="w-10 h-10 rounded-full object-cover border border-slate-700" />
              <div className="flex-1 min-w-0">
                <h4 className="font-bold text-xs text-slate-100 truncate">{currentUser.name}</h4>
                <span className="text-[10px] font-bold text-amber-400">{currentUser.role}</span>
              </div>
            </div>

            <nav className="space-y-1.5 pt-2">
              {[
                { tab: 'dashboard', icon: LayoutDashboard, label: t.dashboard },
                { tab: 'members', icon: Users, label: t.members },
                { tab: 'events', icon: CalendarRange, label: t.events },
                { tab: 'finance', icon: DollarSign, label: t.finance },
                { tab: 'communication', icon: MessageSquare, label: t.communication },
                { tab: 'reports', icon: BarChart3, label: t.reports },
                { tab: 'security', icon: ShieldAlert, label: t.security }
              ].map(item => (
                <button key={item.tab} onClick={() => setActiveTab(item.tab)} className={`w-full py-2.5 px-3.5 rounded-xl text-xs font-semibold flex items-center justify-between transition-all cursor-pointer ${activeTab === item.tab ? 'bg-amber-500 text-slate-950 font-bold' : 'hover:bg-slate-800 text-slate-400'}`}>
                  <item.icon className="w-4.5 h-4.5 text-amber-500" />
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
          </div>
          <div className="p-4 border-t border-slate-800 text-[10px] text-slate-500 text-center font-mono">{t.copticGreeting}</div>
        </aside>

        <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {activeTab === 'dashboard' && (
            <DashboardComponent members={members} events={events} expenses={expenses} donations={donations} logs={logs} onNavigate={setActiveTab} userRole={currentUser.role} />
          )}
          {activeTab === 'members' && (
            <MembersComponent members={members} onAddMember={handleAddMember} onUpdateMember={handleUpdateMember} onDeleteMember={handleDeleteMember} onBulkMessage={() => {}} />
          )}
          {activeTab === 'events' && (
            <EventsComponent events={events} bookings={bookings} onAddEvent={handleAddEvent} onAddBooking={handleAddBooking} onRSVP={() => {}} />
          )}
          {activeTab === 'finance' && (
            <FinanceComponent expenses={expenses} donations={donations} onAddExpense={handleAddExpense} onAddDonation={handleAddDonation} />
          )}
          {activeTab === 'communication' && (
            <CommunicationComponent announcements={announcements} prayerRequests={prayerRequests} chatMessages={chatMessages} onAddAnnouncement={handleAddAnnouncement} onAddPrayerRequest={() => {}} onAddChatMessage={handleAddChatMessage} onSupportPrayer={() => {}} />
          )}
          {activeTab === 'reports' && (
            <ReportsComponent members={members} events={events} expenses={expenses} donations={donations} />
          )}
          {activeTab === 'security' && (
            <SecurityComponent logs={logs} userRole={currentUser.role} />
          )}
        </main>
      </div>
    </div>
  );
}
