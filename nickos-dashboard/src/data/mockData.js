// ─── MOCK DATA — replace with live API calls ────────────────────────────────
// API base: process.env.VITE_API_URL || 'https://nickos-backend.railway.app'

export const mockHabits = [
  { id: 'wake_up',             emoji: '⏰', label: 'Wake by 8am',       hit: true,  streak: 5,  best: 14 },
  { id: 'meal_1',              emoji: '🍳', label: 'Breakfast by 9:30', hit: true,  streak: 3,  best: 21 },
  { id: 'meal_2',              emoji: '🥗', label: 'Lunch by 2:30',     hit: false, streak: 2,  best: 14 },
  { id: 'meal_3',              emoji: '🍽️', label: 'Dinner by 7:30',    hit: false, streak: 3,  best: 19 },
  { id: 'water',               emoji: '💧', label: 'Water (8 glasses)',  hit: true,  streak: 7,  best: 30, value: 5, goal: 8 },
  { id: 'workout',             emoji: '💪', label: 'Workout 5×/wk',     hit: true,  streak: 4,  best: 28 },
  { id: 'sleep',               emoji: '😴', label: 'Sleep by midnight',  hit: false, streak: 5,  best: 22 },
  { id: 'no_smoke_preworkout', emoji: '🚭', label: 'No smoke pre-WO',   hit: true,  streak: 12, best: 45 },
]

export const mockToday = {
  date: new Date(),
  greeting: 'Good morning, Nick',
  health: {
    sleep:   { value: 7.2, goal: 8,   unit: 'hrs',     pct: 90 },
    meals:   { value: 2,   goal: 3,   unit: 'meals',   pct: 67 },
    water:   { value: 5,   goal: 8,   unit: 'glasses', pct: 63 },
    workout: { value: 1,   goal: 1,   unit: 'done',    pct: 100 },
  },
  focus: 'Finish PEAD backtest MVP and push to GitHub before end of day',
  nextNudge: { label: 'Afternoon check-in', minutesAway: 94 },
  isWorkoutDay: true,
  workout: {
    name: 'Push Day A',
    exercises: [
      { name: 'Bench Press',       sets: 4, reps: '6–8',   weight: '155 lb' },
      { name: 'Incline DB Press',  sets: 3, reps: '10–12',  weight: '50 lb' },
      { name: 'Shoulder Press',    sets: 3, reps: '8–10',  weight: '95 lb' },
      { name: 'Lateral Raises',    sets: 3, reps: '15',    weight: '20 lb' },
      { name: 'Tricep Pushdowns',  sets: 3, reps: '12–15', weight: 'cable' },
    ],
    duration: '55–65 min',
  },
  affirmation: {
    text: "You're building something real while everyone else is waiting to be ready. The PEAD bot, the study abroad fight, NickOS — these aren't side projects, they're proof you don't wait for permission. Keep moving.",
    refreshIn: 1800,
  },
  calendar: [
    { id: 1, title: 'Study Abroad Appeal Meeting',  time: '10:00 AM', duration: '1 hr',   color: '#7c3aed' },
    { id: 2, title: 'Advisor Office Hours',          time: '2:30 PM',  duration: '30 min', color: '#3b82f6' },
    { id: 3, title: 'Gym — Push Day',                time: '5:00 PM',  duration: '1 hr',   color: '#10b981' },
  ],
  emails: [
    { id: 1, tag: 'act_now',    from: 'advisor@university.edu',     subject: 'Meeting confirmation — June 15 appeal',         preview: 'Please confirm your 10am slot for the academic appeal review...', time: '8:14 AM' },
    { id: 2, tag: 'opportunity', from: 'upwork@mail.upwork.com',    subject: 'New job match: Python Developer — $65/hr',       preview: 'A client is looking for an algo trading developer with Python...', time: '7:02 AM' },
    { id: 3, tag: 'act_now',    from: 'financial-aid@university.edu', subject: 'Action required: Submit appeal documents',     preview: 'Your appeal packet must be received by June 13...', time: '6:45 AM' },
  ],
}

export const mockHealth = {
  weekStats: {
    sleepAvg:    7.1,
    mealsHitPct: 71,
    waterAvg:    6.2,
    workoutsDone: 4,
    workoutsGoal: 5,
  },
  sleepChart: [
    { day: 'Mon', hrs: 6.5 },
    { day: 'Tue', hrs: 7.0 },
    { day: 'Wed', hrs: 8.1 },
    { day: 'Thu', hrs: 6.8 },
    { day: 'Fri', hrs: 7.5 },
    { day: 'Sat', hrs: 9.0 },
    { day: 'Sun', hrs: 6.9 },
  ],
  streaks: {
    sleep:   { current: 5,  best: 14 },
    meals:   { current: 3,  best: 21 },
    workout: { current: 4,  best: 28 },
    water:   { current: 7,  best: 30 },
  },
  healthScore: {
    total: 74,
    breakdown: {
      sleep:   { score: 80, weight: 0.3 },
      meals:   { score: 65, weight: 0.25 },
      workout: { score: 85, weight: 0.25 },
      water:   { score: 70, weight: 0.2  },
    }
  },
  mealSuggestions: [
    { name: 'Chicken + Rice + Broccoli', cost: 3.40, protein: 52 },
    { name: 'Eggs + Oats + Banana',      cost: 1.20, protein: 28 },
    { name: 'Ground Beef Stir-fry',      cost: 4.10, protein: 46 },
    { name: 'Tuna + Whole Wheat Pasta',  cost: 2.60, protein: 38 },
  ],
  workout: {
    name: 'Push Day A',
    exercises: [
      { name: 'Bench Press',       sets: 4, reps: '6–8',   weight: '155 lb', done: false },
      { name: 'Incline DB Press',  sets: 3, reps: '10–12', weight: '50 lb',  done: false },
      { name: 'Shoulder Press',    sets: 3, reps: '8–10',  weight: '95 lb',  done: false },
      { name: 'Lateral Raises',    sets: 3, reps: '15',    weight: '20 lb',  done: false },
      { name: 'Tricep Pushdowns',  sets: 3, reps: '12–15', weight: 'cable',  done: false },
    ],
    duration: '55–65 min',
    notes: 'Focus on chest stretch at bottom of bench. No ego lifting.',
  },
  healthTip: "Lifting fasted? Make sure you're hitting 0.8–1g protein per lb bodyweight post-workout. At your size, that's 155–175g/day. Eggs for breakfast every day is a cheat code.",
  steps: { today: 6420, goal: 10000, weekAvg: 7800 },
}

export const mockEmails = [
  { id: 1,  tag: 'act_now',    account: 'University',    from: 'advisor@university.edu',           subject: 'Meeting confirmation — June 15 appeal',         preview: 'Please confirm your 10am slot for the academic appeal review. Documents must be submitted 48hrs prior...', time: '8:14 AM', date: 'Today' },
  { id: 2,  tag: 'opportunity', account: 'Personal',     from: 'upwork@mail.upwork.com',           subject: 'New job match: Python Developer — $65/hr',       preview: 'A client is looking for an algo trading developer with Python/pandas expertise for a 3-month contract...', time: '7:02 AM', date: 'Today' },
  { id: 3,  tag: 'act_now',    account: 'University',    from: 'financial-aid@university.edu',     subject: 'Action required: Submit appeal documents',        preview: 'Your appeal packet must be received no later than June 13. Missing documents will result in a denied appeal...', time: '6:45 AM', date: 'Today' },
  { id: 4,  tag: 'opportunity', account: 'Personal',     from: 'no-reply@robinhood.com',           subject: 'Weekly market recap — big movers this week',      preview: 'NVDA up 8.2%, TSLA volatile. Your watchlist had 3 earnings beats...', time: '6:00 AM', date: 'Today' },
  { id: 5,  tag: 'fyi',        account: 'University',    from: 'registrar@university.edu',         subject: 'Fall 2026 registration opens July 1',             preview: 'Priority registration for current students begins July 1 at 8am. Make sure your holds are cleared...', time: 'Yesterday', date: 'Yesterday' },
  { id: 6,  tag: 'fyi',        account: 'Personal',     from: 'github@github.com',                 subject: 'Your repo nickos had 3 commits pushed',           preview: 'Activity summary: 3 commits to main, 1 issue closed, 0 open PRs...', time: 'Yesterday', date: 'Yesterday' },
  { id: 7,  tag: 'opportunity', account: 'Personal',     from: 'sneakercon@events.com',            subject: 'StockX seller fee waiver — this weekend only',    preview: 'List any Jordan 1 or Dunk and pay 0% seller fees through Sunday...', time: 'Yesterday', date: 'Yesterday' },
]

export const mockGoals = [
  {
    id: 1,
    name: 'Algo Trading Bot (PEAD)',
    emoji: '📈',
    description: 'Post-earnings announcement drift backtest → live paper trading',
    progress: 45,
    status: 'active',
    priority: 'high',
    lastUpdated: '2 hours ago',
    nextAction: 'Run PEAD backtest on 2020–2024 S&P 500 earnings data',
    deadline: 'Jun 30',
    wins: ['Data pipeline complete', 'Signal logic drafted', 'backtesting framework set up'],
  },
  {
    id: 2,
    name: 'Study Abroad Appeal',
    emoji: '🎓',
    description: 'Academic appeal to restore eligibility for fall semester abroad',
    progress: 70,
    status: 'active',
    priority: 'critical',
    lastUpdated: '1 day ago',
    nextAction: 'Final review of appeal documents before June 15 meeting',
    deadline: 'Jun 15',
    wins: ['Draft appeal letter written', 'Advisor meeting scheduled', 'Supporting docs gathered'],
  },
  {
    id: 3,
    name: 'Freelance Upwork Profile',
    emoji: '💼',
    description: 'Establish Python/quant dev profile, land first paid gig',
    progress: 20,
    status: 'active',
    priority: 'medium',
    lastUpdated: '3 days ago',
    nextAction: 'Write bio and add 3 portfolio samples to profile',
    deadline: 'Jul 15',
    wins: ['Account created', 'Skills assessment passed'],
  },
  {
    id: 4,
    name: 'NickOS Build',
    emoji: '🖥️',
    description: 'Personal OS dashboard — health, goals, inbox, calendar, all in one',
    progress: 65,
    status: 'active',
    priority: 'high',
    lastUpdated: '1 hour ago',
    nextAction: 'Deploy React dashboard to Vercel, wire up Railway API',
    deadline: 'Jun 20',
    wins: ['Telegram bot live', 'Gmail triage working', 'FastAPI backend deployed', 'Phase 4 complete'],
  },
  {
    id: 5,
    name: 'Sneaker Reselling Bot',
    emoji: '👟',
    description: 'Automate Nike SNKRS / StockX monitoring for profitable drops',
    progress: 10,
    status: 'backlog',
    priority: 'low',
    lastUpdated: '1 week ago',
    nextAction: 'Research SNKRS app API patterns and rate limits',
    deadline: 'Aug 1',
    wins: ['Concept validated'],
  },
]

export const mockWeekly = {
  weekLabel: 'Week of Jun 2 – Jun 8',
  reportCard: {
    sleep:   { grade: 'B+', avg: 7.1, trend: '+0.4 vs last week' },
    meals:   { grade: 'C+', avg: '2.1/3', trend: '-0.2 vs last week' },
    water:   { grade: 'B',  avg: '6.2 glasses', trend: '+1.1 vs last week' },
    workout: { grade: 'A-', done: 4, goal: 5, trend: 'Same as last week' },
    overall: { grade: 'B', score: 74, trend: '+3 pts vs last week' },
  },
  oneThingToImprove: 'Hit all 3 meals every day — you\'re skipping lunch 4 out of 7 days. Prep Sunday, eat Sunday.',
  nextWeekPreview: [
    { day: 'Mon', focus: 'Push Day + PEAD data pull',       reminder: 'Prep meals Sunday night' },
    { day: 'Tue', focus: 'Pull Day + Appeal final review',   reminder: 'Docs due by EOD' },
    { day: 'Wed', focus: 'Rest + Upwork profile writing',   reminder: '3 portfolio samples' },
    { day: 'Thu', focus: 'Legs Day + Backtest run',          reminder: 'Review results' },
    { day: 'Fri', focus: 'Push Day B + NickOS deploy',       reminder: 'Push to Vercel' },
    { day: 'Sat', focus: 'Rest / active recovery',           reminder: 'Meal prep day' },
    { day: 'Sun', focus: 'Rest + Weekly review',             reminder: 'Set intentions' },
  ],
  trendChart: [
    { week: 'W1', score: 58 },
    { week: 'W2', score: 63 },
    { week: 'W3', score: 68 },
    { week: 'W4', score: 71 },
    { week: 'W5', score: 74 },
  ],
}
