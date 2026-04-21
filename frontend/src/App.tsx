import { useState } from "react";
import { Play, Download, Send, CheckCircle2, Circle, BookOpen, Search, Code, GraduationCap, Edit, Library, Activity, FileText, BarChart3, Settings2, LayoutTemplate, Compass, Sparkles, X, MessagesSquare, MessageCircle, ShieldAlert, AlertTriangle, ChevronRight, RotateCcw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function preprocessDraftForMarkdown(draftText: string) {
  const pattern = /\[来源:\s*(.*?),\s*原文:\s*"(.*?)"\]/g;
  return draftText.replace(pattern, (match, sourceId, quote) => {
    let cleanId = sourceId.replace(/Paper_ID:/gi, '').trim();
    if(cleanId.toLowerCase().includes("none") || !cleanId) return "";
    // Output custom markdown link. Title holds the quote.
    return ` [[${cleanId}]](# "${quote.replace(/"/g, '&quot;')}")`;
  });
}

const NODES = [
  { id: "Planner", n: "1", t: "深度课题拆解", d: "多维结构化分析", icon: Search },
  { id: "Screener", n: "2", t: "文献海选筛选", d: "全网并发检索与评分", icon: Library },
  { id: "Reader", n: "3", t: "精细流式研读", d: "多线程核心内容解析", icon: BookOpen },
  { id: "DataMiner", n: "4", t: "数据矩阵提取", d: "提炼图表、结论与术语", icon: Code },
  { id: "Writer", n: "5", t: "综述自动化生成", d: "基于知识图谱的合成", icon: Edit },
  { id: "Critic", n: "6", t: "红队学术批判", d: "生成局限性质疑清单", icon: ShieldAlert }
];

// ================================
// CUSTOM CONCEPT GRAPH ENGINE
// ================================
function parseMermaidGraph(raw: string) {
  const text = raw.replace(/\\n/g, '\n').replace(/^(flowchart|graph)\s+\w+\s*/gm, '');
  const nodeMap = new Map<string, string>();
  const edges: { from: string; to: string }[] = [];
  const pat = /^([A-Za-z0-9_]+)(\[([^\]]+)\])?\s*--[->]+\s*([A-Za-z0-9_]+)(\[([^\]]+)\])?/;
  for (const line of text.split('\n').map(l => l.trim()).filter(Boolean)) {
    const m = line.match(pat);
    if (m) {
      const [, fId,, fLabel, tId,, tLabel] = m;
      if (!nodeMap.has(fId)) nodeMap.set(fId, fLabel || fId);
      if (!nodeMap.has(tId)) nodeMap.set(tId, tLabel || tId);
      edges.push({ from: fId, to: tId });
    } else {
      const nm = line.match(/^([A-Za-z0-9_]+)\[([^\]]+)\]/);
      if (nm) nodeMap.set(nm[1], nm[2]);
    }
  }
  return { nodeMap, edges };
}

function buildTreeLayout(nodeMap: Map<string, string>, edges: { from: string; to: string }[]) {
  const NW = 164, NH = 46, HG = 52, VG = 16;
  const ids = Array.from(nodeMap.keys());
  if (!ids.length) return { positions: new Map<string, { x: number; y: number }>(), depthMap: new Map<string, number>(), NW, NH, svgW: 400, svgH: 200 };
  const childMap = new Map<string, string[]>();
  const parentSet = new Set<string>();
  for (const { from, to } of edges) {
    if (!childMap.has(from)) childMap.set(from, []);
    childMap.get(from)!.push(to);
    parentSet.add(to);
  }
  const roots = ids.filter(id => !parentSet.has(id));
  const root = roots[0] || ids[0];
  const depthMap = new Map<string, number>([[root, 0]]);
  const bq = [root];
  while (bq.length) {
    const cur = bq.shift()!;
    for (const ch of childMap.get(cur) || []) {
      if (!depthMap.has(ch)) { depthMap.set(ch, depthMap.get(cur)! + 1); bq.push(ch); }
    }
  }
  for (const id of ids) { if (!depthMap.has(id)) depthMap.set(id, 0); }
  const byCol = new Map<number, string[]>();
  for (const [id, d] of depthMap.entries()) {
    if (!byCol.has(d)) byCol.set(d, []);
    byCol.get(d)!.push(id);
  }
  const maxD = Math.max(...Array.from(depthMap.values()));
  const maxPerCol = Math.max(...Array.from(byCol.values()).map(v => v.length));
  const svgH = Math.max(240, maxPerCol * (NH + VG) + 80);
  const svgW = (maxD + 1) * (NW + HG) + 48;
  const positions = new Map<string, { x: number; y: number }>();
  for (const [d, colIds] of byCol.entries()) {
    const colH = colIds.length * (NH + VG) - VG;
    const startY = (svgH - colH) / 2;
    colIds.forEach((id, i) => { positions.set(id, { x: d * (NW + HG) + 24, y: startY + i * (NH + VG) }); });
  }
  return { positions, depthMap, NW, NH, svgW, svgH };
}

const GRAPH_COLORS = [
  { bg: '#eef2ff', border: '#6366f1', text: '#3730a3', glow: 'rgba(99,102,241,0.2)' },
  { bg: '#f0fdf4', border: '#22c55e', text: '#14532d', glow: 'rgba(34,197,94,0.15)' },
  { bg: '#fdf4ff', border: '#a855f7', text: '#581c87', glow: 'rgba(168,85,247,0.15)' },
  { bg: '#fff7ed', border: '#f97316', text: '#7c2d12', glow: 'rgba(249,115,22,0.15)' },
  { bg: '#f0f9ff', border: '#0ea5e9', text: '#0c4a6e', glow: 'rgba(14,165,233,0.15)' },
];

function CustomConceptGraph({ chart }: { chart: string }) {
  const [pos, setPos] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<string | null>(null);
  const { nodeMap, edges } = parseMermaidGraph(chart);
  const { positions, depthMap, NW, NH, svgW, svgH } = buildTreeLayout(nodeMap, edges);
  const onWheel = (e: React.WheelEvent) => setPos(p => ({ ...p, scale: Math.max(0.15, Math.min(p.scale - e.deltaY * 0.0008, 3)) }));
  const onMD = (e: React.MouseEvent) => { setIsDragging(true); setDragStart({ x: e.clientX - pos.x, y: e.clientY - pos.y }); };
  const onMM = (e: React.MouseEvent) => { if (!isDragging) return; setPos(p => ({ ...p, x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })); };
  const onMU = () => setIsDragging(false);
  return (
    <div className="relative w-full h-[640px] rounded-[28px] overflow-hidden cursor-grab active:cursor-grabbing bg-gradient-to-br from-slate-50 via-white to-indigo-50/50 border border-indigo-100 shadow-[0_8px_48px_rgba(99,102,241,0.07)]"
      onWheel={onWheel} onMouseDown={onMD} onMouseMove={onMM} onMouseUp={onMU} onMouseLeave={onMU}>
      {/* Dot grid */}
      <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #ddd6fe 1.5px, transparent 0)', backgroundSize: '28px 28px', opacity: 0.6 }} />
      {/* Radial center glow */}
      <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(238,242,255,0.8), transparent)' }} />
      {/* Controls */}
      <div className="absolute top-4 right-4 flex gap-2 z-10">
        <button onClick={() => setPos({ x: 0, y: 0, scale: 1 })} className="flex items-center gap-1.5 px-3 py-2 bg-white/90 backdrop-blur border border-indigo-100 text-indigo-600 text-[11px] font-bold rounded-xl hover:bg-indigo-50 shadow-sm transition-all">
          <RotateCcw className="w-3 h-3" /> Reset
        </button>
        <div className="px-3 py-2 bg-white/70 backdrop-blur border border-neutral-200/60 text-neutral-400 text-[10px] font-bold uppercase tracking-widest rounded-xl shadow-sm">Scroll · Drag</div>
      </div>
      {/* Graph */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
        <div className="pointer-events-auto" style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${pos.scale})`, transformOrigin: 'center', transition: isDragging ? 'none' : 'transform 0.04s' }}>
          <svg width={svgW} height={svgH} style={{ overflow: 'visible' }}>
            <defs>
              <marker id="cg-arr" markerWidth="7" markerHeight="5" refX="6" refY="2.5" orient="auto">
                <path d="M0,0 L7,2.5 L0,5 Z" fill="#a5b4fc" />
              </marker>
            </defs>
            {edges.map(({ from, to }, i) => {
              const fp = positions.get(from), tp = positions.get(to);
              if (!fp || !tp) return null;
              const x1 = fp.x + NW, y1 = fp.y + NH / 2, x2 = tp.x, y2 = tp.y + NH / 2;
              const cx = (x1 + x2) / 2;
              return (
                <g key={i}>
                  <motion.path 
                    initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 1, delay: i * 0.05 }}
                    d={`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`} 
                    stroke="url(#cg-grad)" strokeWidth="2" fill="none" markerEnd="url(#cg-arr)" strokeLinecap="round" 
                  />
                </g>
              );
            })}
            {Array.from(positions.entries()).map(([id, { x, y }]) => {
              const label = nodeMap.get(id) || id;
              const depth = depthMap.get(id) || 0;
              const col = GRAPH_COLORS[Math.min(depth, GRAPH_COLORS.length - 1)];
              const isHov = hovered === id;
              const isRoot = depth === 0;
              const displayLabel = label.length > 15 ? label.slice(0, 15) + '…' : label;
              return (
                <motion.g key={id} 
                  initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: depth * 0.1 }}
                  onMouseEnter={() => setHovered(id)} onMouseLeave={() => setHovered(null)} style={{ cursor: 'pointer' }}>
                  {/* Glassmorphic Node */}
                  <rect x={x} y={y} width={NW} height={NH} rx={isRoot ? 20 : 12}
                    fill={isHov ? col.border : 'white'} fillOpacity={isHov ? 0.9 : 0.8}
                    stroke={col.border} strokeWidth={isRoot ? 3 : 2}
                    className="shadow-xl"
                    style={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', backdropFilter: 'blur(8px)' }}
                  />
                  <text x={x + NW / 2} y={y + NH / 2} textAnchor="middle" dominantBaseline="middle"
                    fontSize={isRoot ? 14 : 12} fontWeight={isRoot ? '800' : '600'}
                    fontFamily="Inter, system-ui, sans-serif" fill={isHov ? 'white' : col.text}
                    className="pointer-events-none select-none"
                    style={{ transition: 'fill 0.3s' }}>
                    {displayLabel}
                  </text>
                  {isHov && (
                    <circle cx={x + NW} cy={y + NH / 2} r={4} fill={col.border} className="animate-ping" />
                  )}
                </motion.g>
              );
            })}
          </svg>
          <svg width="0" height="0">
            <defs>
              <linearGradient id="cg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#818cf8" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#c7d2fe" stopOpacity="0.4" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </div>
      {/* Legend */}
      <div className="absolute bottom-4 left-5 flex items-center gap-4 pointer-events-none">
        {GRAPH_COLORS.slice(0, 4).map((c, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full border" style={{ background: c.bg, borderColor: c.border }} />
            <span className="text-[10px] font-semibold text-neutral-400">{['核心概念', '一级分支', '二级分支', '三级分支'][i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [topic, setTopic] = useState("Explainable Deep Learning in Medical Imaging Context");
  const [minPapers, setMinPapers] = useState(5);
  const [threadId, setThreadId] = useState("");
  const [currentNode, setCurrentNode] = useState("Pending");
  const [stateValues, setStateValues] = useState<any>({});
  const [isSuspended, setIsSuspended] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const [activeTab, setActiveTab] = useState("orchestrator");
  const [hitlQuestions, setHitlQuestions] = useState("");
  
  // Phase 8: Logs & History
  const [logs, setLogs] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>(() => {
    const saved = localStorage.getItem("ds_history");
    return saved ? JSON.parse(saved) : [];
  });
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  // Copilot State
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [copilotHistory, setCopilotHistory] = useState<{role:string, content:string}[]>([]);
  const [copilotMsg, setCopilotMsg] = useState("");
  const [quoteTooltip, setQuoteTooltip] = useState<{x:number, y:number, text:string} | null>(null);

  const saveToHistory = (newThread: string, topicName: string) => {
    const item = { id: newThread, topic: topicName, time: new Date().toLocaleString() };
    const updated = [item, ...history.filter(h => h.id !== newThread)].slice(0, 10);
    setHistory(updated);
    localStorage.setItem("ds_history", JSON.stringify(updated));
  };

  const handleTextSelection = () => {
     const selection = window.getSelection();
     if(selection && selection.toString().trim().length > 5 && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        setQuoteTooltip({
           x: rect.left + rect.width / 2, 
           y: rect.top - 15, 
           text: selection.toString().trim()
        });
     } else {
        setQuoteTooltip(null);
     }
  };

  const askAboutQuote = () => {
      if(!quoteTooltip) return;
      setIsCopilotOpen(true);
      setCopilotMsg(`> ${quoteTooltip.text}\n\n请结合文献上下文，为我详细通俗地解释这部分内容的意思：`);
      setQuoteTooltip(null);
  };

  const askAboutJargon = (term: string) => {
      setIsCopilotOpen(true);
      setCopilotMsg(`请结合我们当前阅读的这批文献，为我深度、通俗地全面展开讲讲什么是【${term}】？`);
  };

  const startResearch = async (payload: any) => {
    setIsLoading(true);
    if (payload.topic) saveToHistory(payload.thread_id, payload.topic);
    
    try {
      const response = await fetch("http://localhost:8000/api/research", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (chunk.startsWith("data: ")) {
            const dataStr = chunk.slice(6);
            if (dataStr) {
               try {
                  const data = JSON.parse(dataStr);
                  if(!data.error) {
                      // 🔴 Phase 8: 细粒度事件处理
                      if (data.type === "thought") {
                          setLogs(prev => [...prev, { content: data.content, node: data.node, time: new Date().toLocaleTimeString() }]);
                      } else if (data.type === "state_update") {
                          const { node, state_values, next_nodes } = data;
                          if(node) setCurrentNode(node);
                          if(state_values) {
                              setStateValues(state_values);
                              if(node === "Planner") setHitlQuestions(state_values.sub_questions?.join("\\n") || "");
                              if(state_values.draft) setActiveTab("manuscript");
                          }
                          // 🔴 Phase 8: HITL Breakpoints
                          if(next_nodes?.includes("Screener") && node === "Planner") {
                              setIsSuspended(true); setCurrentNode("Suspended");
                              setActiveTab("screening"); // 自动平滑跳转
                          }
                          if(next_nodes?.includes("Reader") && node === "Screener") {
                              setIsSuspended(true); setCurrentNode("Reviewing Papers");
                              setActiveTab("screening"); // 自动平滑跳转
                          }
                          if(next_nodes?.length === 0 && node && node !== "Planner") setCurrentNode("Completed");
                      }
                  }
               } catch(err) {}
            }
          }
          boundary = buffer.indexOf("\n\n");
        }
      }
    } finally { setIsLoading(false); }
  };

  const manualDiscovery = async () => {
    if (!threadId) return;
    setIsLoading(true);
    setLogs(prev => [...prev, { content: "⚡ 手动触发实时追踪：正在检索该领域最新突破...", node: "Discovery", time: new Date().toLocaleTimeString() }]);
    
    try {
      const response = await fetch("http://localhost:8000/api/discovery", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId }),
      });
      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        const lines = text.split('\n\n');
        for(let line of lines) {
           if(line.startsWith("data: ")) {
              try {
                 const data = JSON.parse(line.slice(6));
                 if(data.type === "thought") setLogs(prev => [...prev, { content: data.content, node: data.node, time: new Date().toLocaleTimeString() }]);
                 if(data.type === "state_update") setStateValues(data.state_values);
              } catch(e) {}
           }
        }
      }
    } finally { setIsLoading(false); }
  };

  const handlePdfUpload = async (file: File) => {
    if (!threadId || !file) return;
    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("thread_id", threadId);

    try {
      const res = await fetch("http://localhost:8000/api/upload_pdf", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success) {
         setLogs(prev => [...prev, { content: `📂 [本地导入成功] ${file.name} 已并入研究池。`, node: "System", time: new Date().toLocaleTimeString() }]);
         // Refresh state
         const sres = await fetch(`http://localhost:8000/api/state/${threadId}`);
         const sdata = await sres.json();
         setStateValues(sdata.values);
      }
    } finally { setIsLoading(false); }
  };

  const loadHistory = async (id: string, topicStr: string) => {
    setThreadId(id);
    setTopic(topicStr);
    setIsLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/state/${id}`);
      const data = await res.json();
      setStateValues(data.values);
      setIsSuspended(data.next.length > 0);
      if(data.next.length > 0) setCurrentNode("Suspended");
      else setCurrentNode("Completed");
    } finally { setIsLoading(false); setIsHistoryOpen(false); }
  };

  const onRunPipeline = () => {
    const thread = `session_${Math.random().toString(36).substring(7)}`;
    setThreadId(thread); setIsSuspended(false); setStateValues({}); setCurrentNode("Pending"); setActiveTab("orchestrator");
    startResearch({ topic, min_papers: minPapers, thread_id: thread });
  };

  const onConfirm = () => {
    setIsSuspended(false);
    startResearch({ topic, thread_id: threadId, sub_questions: hitlQuestions.split("\\n").filter(q=>q.trim())});
  };

  const onAskCopilot = async () => {
     if(!copilotMsg.trim()) return;
     const newHist = [...copilotHistory, { role: "user", content: copilotMsg }];
     setCopilotHistory(newHist);
     setCopilotMsg("");
     
     try {
       const res = await fetch("http://localhost:8000/api/copilot", {
         method: "POST", headers:{"Content-Type":"application/json"},
         body: JSON.stringify({ thread_id: threadId, message: copilotMsg })
       });
       if(!res.body) return;
       const reader = res.body.getReader();
       const decoder = new TextDecoder();
       let assistantReply = "";
       let updatedHist = [...newHist, { role: "assistant", content: "" }];
       setCopilotHistory(updatedHist);
       
       while(true) {
         const { value, done } = await reader.read();
         if(done) break;
         const text = decoder.decode(value);
         const lines = text.split('\n\n');
         
         for(let line of lines) {
            if(line.startsWith("data: ")) {
               try {
                  const data = JSON.parse(line.slice(6));
                  if(data.token) {
                     assistantReply += data.token;
                     updatedHist[updatedHist.length - 1].content = assistantReply;
                     setCopilotHistory([...updatedHist]);
                  }
               } catch(e) {}
            }
         }
       }
     } catch(err) {
       console.error(err);
     }
  };

  return (
    <div className="flex h-screen bg-neutral-50 font-sans text-neutral-900 overflow-hidden">
      
      {/* 4. Navigation & Workspace */}
      <div className="flex flex-1 overflow-hidden relative">

      {/* 1. Premium Navigation Sidebar */}
      <aside className="w-[72px] bg-white border-r border-neutral-200 flex flex-col items-center py-6 shrink-0 z-30 shadow-sm relative">
        <div className="w-11 h-11 bg-indigo-600 rounded-2xl flex items-center justify-center text-white font-black text-sm shadow-lg shadow-indigo-600/30 mb-10 select-none">
          DS
        </div>
        <nav className="flex flex-col gap-3 w-full items-center px-2">
          {[
            { id: "orchestrator", icon: LayoutTemplate, tt: "智能编排" },
            { id: "screening", icon: MessagesSquare, tt: "协同中心" },
            { id: "concept", icon: Compass, tt: "领域雷达" },
            { id: "library", icon: Library, tt: "原始文献库" },
            { id: "analytics", icon: BarChart3, tt: "分析看板" },
            { id: "critic", icon: ShieldAlert, tt: "红队批判" },
            { id: "manuscript", icon: FileText, tt: "综述工坊" }
          ].map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)} title={t.tt}
              className={`relative w-12 h-12 flex flex-col items-center justify-center rounded-2xl transition-all group ${
                activeTab === t.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600'
              }`}>
              <t.icon className="w-5 h-5" />
            </button>
          ))}
          <div className="w-8 h-[1px] bg-neutral-100 my-2" />
          <button onClick={() => setIsHistoryOpen(true)} className="w-12 h-12 flex items-center justify-center rounded-2xl text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 transition-all" title="历史研究档案">
            <RotateCcw className="w-5 h-5" />
          </button>
        </nav>
        <div className="mt-auto px-2 w-full space-y-3">
          <button className="w-12 h-12 flex items-center justify-center rounded-2xl text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-all">
             <Settings2 className="w-5 h-5" />
          </button>
        </div>
      </aside>

      {/* History Drawer Overlay */}
      <AnimatePresence>
        {isHistoryOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setIsHistoryOpen(false)} className="fixed inset-0 bg-neutral-900/20 backdrop-blur-sm z-40" />
            <motion.div initial={{ x: -300 }} animate={{ x: 72 }} exit={{ x: -300 }} className="fixed top-0 bottom-0 w-[300px] bg-white z-50 border-r border-neutral-200 shadow-2xl p-6 flex flex-col">
              <div className="flex justify-between items-center mb-8">
                <h3 className="text-lg font-bold text-neutral-800 tracking-tight">历史研究档案</h3>
                <button onClick={() => setIsHistoryOpen(false)} className="p-2 hover:bg-neutral-100 rounded-lg"><X className="w-4 h-4" /></button>
              </div>
              <div className="flex-1 overflow-y-auto space-y-3">
                {history.map((h, i) => (
                  <button key={i} onClick={() => loadHistory(h.id, h.topic)} className="w-full p-4 rounded-xl border border-neutral-100 text-left hover:border-indigo-300 hover:bg-indigo-50/30 transition-all group">
                    <p className="text-sm font-bold text-neutral-700 group-hover:text-indigo-700 line-clamp-1">{h.topic}</p>
                    <p className="text-[10px] text-neutral-400 mt-1 uppercase tracking-wider">{h.time}</p>
                  </button>
                ))}
                {history.length === 0 && <p className="text-center text-sm text-neutral-400 mt-20 italic">暂无历史记录</p>}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* 2. Secondary Context Panel (Configuration & Log Console) */}
      <aside className="w-[300px] lg:w-[340px] bg-white border-r border-neutral-200 flex flex-col shrink-0 z-10 relative">
        <div className="p-6 bg-white border-b border-neutral-100 flex items-center justify-between">
           <div>
             <h2 className="text-lg font-bold text-neutral-800 tracking-tight">指挥中心</h2>
             <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest">Mission Control</p>
           </div>
           <button onClick={manualDiscovery} disabled={!threadId || isLoading} className="p-2.5 bg-indigo-50 text-indigo-600 rounded-xl hover:bg-indigo-100 transition-all" title="手动触发实时追踪">
             <Activity className={`w-5 h-5 ${isLoading ? 'animate-pulse' : ''}`} />
           </button>
        </div>
        
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col bg-neutral-50/50">
           {/* Form Section */}
           <div className="p-6 bg-white/40 backdrop-blur-sm space-y-6 border-b border-neutral-100">
              <div>
                <label className="block text-[10px] font-extrabold text-neutral-400 uppercase tracking-widest mb-3">研究课题定义 / Topic Intelligence</label>
                <textarea 
                  value={topic} onChange={e => setTopic(e.target.value)}
                  className="w-full h-24 p-4 bg-white/50 border border-neutral-200 rounded-2xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 text-sm font-medium resize-none transition-all outline-none shadow-sm"
                  placeholder="请输入您的研究领域或特定课题..."
                />
              </div>

              <div className="flex gap-4">
                 <div className="flex-1">
                    <label className="block text-[10px] font-extrabold text-neutral-400 uppercase tracking-widest mb-2">文献容量</label>
                    <select value={minPapers} onChange={e => setMinPapers(Number(e.target.value))} className="w-full p-2.5 bg-white/80 border border-neutral-200 rounded-xl text-xs font-bold outline-none cursor-pointer shadow-sm">
                      <option value={5}>5 篇文献 (快读)</option>
                      <option value={10}>10 篇文献 (标准)</option>
                      <option value={20}>20 篇文献 (深度)</option>
                    </select>
                 </div>
                 <div className="flex-1">
                    <label className="block text-[10px] font-extrabold text-neutral-400 uppercase tracking-widest mb-2">本地 PDF 注入</label>
                    <label className="w-full p-2.5 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-xl text-xs font-bold flex items-center justify-center cursor-pointer hover:bg-indigo-100 transition-all shadow-sm">
                       <Download className="w-3 h-3 mr-2" /> 点击上传
                       <input type="file" className="hidden" accept=".pdf" onChange={e => e.target.files && handlePdfUpload(e.target.files[0])} />
                    </label>
                 </div>
              </div>

              <button 
                onClick={onRunPipeline} disabled={isLoading && !isSuspended}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold shadow-xl shadow-indigo-600/30 transition-all flex items-center justify-center disabled:opacity-50">
                {isLoading && !isSuspended ? <RotateCcw className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 mr-3" />}
                {isLoading && !isSuspended ? "正在加速合成中..." : "启动多智能体引擎"}
              </button>
           </div>

           {/* Thought Log Console (The Brain) - Redesigned as Glassmorphism */}
           <div className="flex-1 p-6 flex flex-col min-h-[300px]">
              <label className="block text-[10px] font-extrabold text-neutral-400 uppercase tracking-widest mb-4 flex items-center">
                 <Sparkles className="w-3 h-3 mr-2 text-indigo-500" /> Agent 思维心跳流 / Thought Stream
              </label>
              <div className="flex-1 bg-white/60 backdrop-blur-xl rounded-[24px] p-5 font-medium text-[11px] leading-relaxed relative overflow-hidden border border-white shadow-[0_8px_32px_rgba(31,38,135,0.07)]">
                 <div className="absolute top-0 left-0 w-full h-[1.5px] bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent" />
                 <div className="h-full overflow-y-auto space-y-3 custom-scrollbar pr-2">
                    {logs.map((log, i) => (
                      <div key={i} className="flex gap-3 animate-in fade-in slide-in-from-left-2 duration-300">
                         <span className="text-neutral-400 font-mono shrink-0">[{log.time}]</span>
                         <span className={`${
                            log.node === 'System' ? 'text-indigo-600' : 
                            log.node === 'Discovery' ? 'text-amber-600' :
                            'text-neutral-700'
                         } font-bold`}>{log.content}</span>
                      </div>
                    ))}
                    {logs.length === 0 && <span className="text-neutral-300 italic">等待智能体协同活动...</span>}
                    <div className="h-4" />
                 </div>
              </div>
           </div>
        </div>
      </aside>

      {/* 3. Main Workspace Area */}
      <main className="flex-1 bg-[#F8F9FB] relative overflow-y-auto custom-scrollbar flex flex-col items-stretch">
         <div className="absolute inset-0 bg-noise opacity-[0.03] pointer-events-none" />
         <div className="flex-1 w-full max-w-[1400px] mx-auto p-6 md:p-10 2xl:p-14 relative z-10">
            
            {activeTab === "screening" && (
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="pt-4 h-full flex flex-col">
                  {currentNode === "Reviewing Papers" ? (
                     <div className="flex-1 flex flex-col bg-white rounded-[32px] border border-neutral-200 overflow-hidden shadow-sm">
                         <div className="p-8 border-b border-neutral-100 flex justify-between items-center bg-gradient-to-r from-indigo-600 to-indigo-700 text-white">
                            <div>
                               <h2 className="text-2xl font-bold flex items-center gap-3">
                                  <Library className="w-7 h-7" /> 文献精确筛选中心
                               </h2>
                               <p className="text-indigo-100 text-sm mt-1 font-medium italic opacity-90">DeepScholar 正在等待您的最终裁决：请从以下候选文献中挑选出最具研究价值的篇目。</p>
                            </div>
                            <button onClick={() => {
                                const selectedIds = stateValues.selected_papers?.map((p:any) => p.paper_id) || [];
                                setIsSuspended(false);
                                startResearch({ thread_id: threadId, selected_paper_ids: selectedIds });
                                setActiveTab("orchestrator");
                            }} className="px-8 py-3 bg-white text-indigo-700 rounded-2xl font-bold hover:bg-neutral-50 transition-all shadow-xl hover:scale-105 active:scale-95">确认甄选结果 ({stateValues.selected_papers?.length || 0})</button>
                         </div>
                         <div className="flex-1 overflow-y-auto p-10 grid grid-cols-1 xl:grid-cols-2 gap-6 bg-neutral-50/30">
                            {stateValues.candidate_papers?.map((paper:any, i:number) => {
                               const isSelected = stateValues.selected_papers?.some((p:any) => p.paper_id === paper.paper_id);
                               return (
                                <div key={i} onClick={() => {
                                    let newSelected = [...(stateValues.selected_papers || [])];
                                    if (isSelected) newSelected = newSelected.filter((p:any) => p.paper_id !== paper.paper_id);
                                    else newSelected.push(paper);
                                    setStateValues({...stateValues, selected_papers: newSelected});
                                  }} className={`p-6 rounded-3xl border-2 cursor-pointer transition-all group relative overflow-hidden ${isSelected ? 'border-indigo-500 bg-white shadow-xl scale-[1.02]' : 'border-neutral-100 bg-white/60 hover:border-indigo-200'}`}>
                                      <div className="flex justify-between items-start mb-4">
                                        <span className={`text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-tighter ${isSelected ? 'bg-indigo-600 text-white' : 'bg-neutral-100 text-neutral-400'}`}>{paper.year || 'N/A'}</span>
                                        {isSelected ? <CheckCircle2 className="w-6 h-6 text-indigo-500" /> : <Circle className="w-6 h-6 text-neutral-200 group-hover:text-indigo-200" />}
                                      </div>
                                      <h4 className={`text-lg font-bold leading-tight mb-3 transition-colors ${isSelected ? 'text-indigo-900' : 'text-neutral-800 group-hover:text-indigo-700'}`}>{paper.title}</h4>
                                      <p className="text-[13px] text-neutral-500 line-clamp-4 leading-relaxed font-medium">{paper.abstract}</p>
                                      {isSelected && <div className="absolute top-0 right-0 w-16 h-16 bg-indigo-500/5 blur-2xl rounded-full" />}
                                  </div>
                               )
                            })}
                         </div>
                     </div>
                  ) : currentNode === "Suspended" ? (
                     <div className="flex-1 flex items-center justify-center p-10">
                        <div className="max-w-3xl w-full bg-white rounded-[40px] p-12 border border-neutral-200 shadow-2xl relative overflow-hidden">
                           <div className="absolute -top-10 -right-10 w-40 h-40 bg-amber-50 rounded-full blur-3xl opacity-50" />
                           <div className="flex items-center gap-5 mb-8 relative">
                              <div className="p-4 bg-amber-500 rounded-3xl text-white shadow-lg shadow-amber-500/30">
                                 <AlertTriangle className="w-8 h-8 animate-pulse" />
                              </div>
                              <div>
                                 <h3 className="text-2xl font-black text-neutral-800 tracking-tight">研究路径确认 (Research Plan Review)</h3>
                                 <p className="text-neutral-400 text-sm font-medium mt-1">Agent 已自动拆解课题，请审阅并微调研究子问题的覆盖广度。</p>
                              </div>
                           </div>
                           <div className="relative mb-8">
                              <textarea 
                                 value={hitlQuestions} onChange={e => setHitlQuestions(e.target.value)} 
                                 className="w-full h-64 p-8 bg-neutral-50 border-2 border-neutral-100 rounded-[32px] text-lg font-medium focus:ring-8 focus:ring-amber-500/5 focus:border-amber-500/30 outline-none transition-all resize-none shadow-inner" 
                                 placeholder="在此调整研究子问题..."
                              />
                              <div className="absolute top-4 right-4 text-[10px] font-black text-amber-500/40 uppercase">Edit Live</div>
                           </div>
                           <button onClick={() => { onConfirm(); setActiveTab("orchestrator"); }} className="w-full py-5 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-[24px] font-black text-lg shadow-2xl shadow-amber-500/20 transition-all hover:scale-[1.01] active:scale-95">批准研究计划并启动引擎</button>
                        </div>
                     </div>
                  ) : (
                     <div className="flex flex-col items-center justify-center h-[600px] border-2 border-dashed border-neutral-200 rounded-[40px] bg-neutral-50/50">
                        <div className="w-20 h-20 bg-white rounded-3xl flex items-center justify-center shadow-sm mb-6">
                           <MessagesSquare className="w-10 h-10 text-neutral-200" />
                        </div>
                        <h3 className="text-xl font-bold text-neutral-400">目前没有待处理的协同任务</h3>
                        <p className="text-neutral-400 text-sm mt-2 font-medium">当 Agent 需要您进行文献筛选或计划确认时，此处会自动激活。</p>
                     </div>
                  )}
               </motion.div>
            )}

            {activeTab === "orchestrator" && (
               <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4">
                  <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">智能协作看板</h1>
                  <p className="text-neutral-500 mb-12 max-w-2xl font-medium">实时可视化 DeepScholar 多智能体推理图谱。系统正自主完成文献调取、精读、挖掘与综述合成。</p>
                  
                  <div className="bg-white/50 backdrop-blur-sm rounded-[40px] border border-neutral-200 p-12 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.03)] relative overflow-hidden">
                      {/* Flowing Connection Line (Background) */}
                      <div className="absolute left-[72px] lg:left-[88px] top-10 bottom-10 w-[3px] bg-neutral-100/50" />
                      <div className="absolute left-[72px] lg:left-[88px] top-10 bottom-10 w-[3px]">
                         <motion.div 
                           initial={{ height: 0 }} animate={{ height: '100%' }} transition={{ duration: 2, ease: "easeInOut" }}
                           className="w-full bg-gradient-to-b from-indigo-500 via-purple-500 to-emerald-500 shadow-[0_0_15px_rgba(99,102,241,0.4)]"
                         />
                      </div>

                      {NODES.map((node, i) => {
                         const isActive = node.id === currentNode || 
                                         (currentNode === "Suspended" && node.id === "Planner") ||
                                         (currentNode === "Reviewing Papers" && node.id === "Screener");
                         
                         const nodeIdx = NODES.findIndex(n => n.id === node.id);
                         let currentIdx = NODES.findIndex(n => n.id === currentNode);
                         if (currentNode === "Suspended") currentIdx = 0; // Planner
                         if (currentNode === "Reviewing Papers") currentIdx = 1; // Screener
                         if (currentNode === "Completed") currentIdx = 99;

                         const isCompleted = currentIdx > nodeIdx;
                         const isPending = !isActive && !isCompleted;

                         return (
                            <div key={node.id} className="relative flex items-center mb-12 last:mb-0">
                               {/* Node Icon with Pulse Effect */}
                               <div className="relative">
                                  {isActive && (
                                     <motion.div 
                                       initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1.5, opacity: [0, 0.4, 0] }}
                                       transition={{ repeat: Infinity, duration: 2 }}
                                       className="absolute inset-0 bg-indigo-500 rounded-3xl"
                                     />
                                  )}
                                  <div className={`w-14 h-14 lg:w-16 lg:h-16 rounded-[22px] lg:rounded-[26px] flex items-center justify-center relative z-10 transition-all duration-700 shadow-lg ${
                                     isActive ? 'bg-indigo-600 text-white translate-x-1 scale-110 shadow-indigo-500/40' : 
                                     isCompleted ? 'bg-emerald-500 text-white shadow-emerald-500/20' :
                                     'bg-white border-2 border-neutral-100 text-neutral-300'
                                  }`}>
                                     <node.icon className={`w-6 h-6 lg:w-7 lg:h-7 ${isActive ? 'animate-pulse' : ''}`} />
                                     {isCompleted && (
                                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute -top-1 -right-1 bg-white rounded-full p-0.5 shadow-md">
                                           <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        </motion.div>
                                     )}
                                  </div>
                               </div>

                               {/* Glassmorphic Description Card */}
                               <motion.div 
                                 initial={false}
                                 animate={{ 
                                    x: isActive ? 12 : 0,
                                    opacity: isPending ? 0.4 : 1,
                                    scale: isActive ? 1.02 : 1
                                 }}
                                 className={`ml-10 lg:ml-12 p-6 lg:p-8 rounded-[28px] lg:rounded-[32px] flex-1 max-w-xl transition-all duration-500 border relative overflow-hidden ${
                                    isActive ? 'bg-white shadow-[0_30px_60px_-12px_rgba(99,102,241,0.12)] border-indigo-100' : 
                                    isCompleted ? 'bg-emerald-50/40 border-emerald-100/50' :
                                    'bg-white/40 border-neutral-100'
                                 }`}>
                                  {isActive && <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500" />}
                                  <div className="flex justify-between items-center mb-2">
                                     <h4 className={`text-base lg:text-lg font-black tracking-tight ${isActive ? 'text-indigo-950' : isCompleted ? 'text-emerald-900' : 'text-neutral-400'}`}>
                                        {node.t}
                                     </h4>
                                     <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full ${
                                        isActive ? 'bg-indigo-100 text-indigo-600' : isCompleted ? 'bg-emerald-100 text-emerald-700' : 'bg-neutral-100 text-neutral-400'
                                     }`}>
                                        Step 0{node.n}
                                     </span>
                                  </div>
                                  <p className={`text-[13px] lg:text-[14px] font-medium leading-relaxed ${isActive ? 'text-indigo-600/80' : 'text-neutral-500'}`}>
                                     {node.d}
                                  </p>
                               </motion.div>
                            </div>
                         )
                      })}
                   </div>
                </motion.div>
             )}

            {activeTab === "concept" && (
                 <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4">
                    <div className="flex items-center justify-between mb-8">
                       <div>
                          <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">领域概念雷达</h1>
                          <p className="text-neutral-500 font-medium">AI 自动生成的领域全景脉络图，帮助您快速建立认知骨架。支持拖拽漫游和缩放探索。</p>
                       </div>
                       {stateValues?.concept_map && (
                          <div className="flex items-center gap-2 px-4 py-2 bg-indigo-50 border border-indigo-100 rounded-xl">
                             <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                             <span className="text-xs font-bold text-indigo-700">Concept Map Active</span>
                          </div>
                       )}
                    </div>
                    
                    {stateValues?.concept_map ? (
                        <CustomConceptGraph chart={stateValues.concept_map} />
                     ) : (
                        <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-indigo-100 rounded-[28px] bg-gradient-to-br from-slate-50 to-indigo-50/30 h-[500px]">
                           <div className="w-20 h-20 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-6">
                              <Compass className="w-10 h-10 text-indigo-300" />
                           </div>
                           <h3 className="text-lg font-bold text-neutral-700 mb-2">领域雷达图待机中</h3>
                           <p className="text-neutral-400 text-sm text-center max-w-[260px]">运行研究流水线后，AI 将在此处自动生成领域全景概念拓扑树。</p>
                        </div>
                     )}
                 </motion.div>
            )}

            {activeTab === "analytics" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4">
                  <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">学术数据情报</h1>
                  <p className="text-neutral-500 mb-12 font-medium">由数据挖掘智能体自动从文献矩阵中提取的定量数据、研究方法与前沿结论。</p>
                  
                  {stateValues?.quantitative_data ? (
                     <div className="grid grid-cols-1 gap-6">
                        {stateValues.quantitative_data.map((dataObj:any, idx:number) => (
                           <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: idx * 0.1 }} key={idx} className="bg-white p-6 rounded-2xl border border-neutral-200 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-lg transition-all flex flex-col">
                              <div className="flex justify-between items-start mb-4">
                                <h3 className="text-lg font-bold text-indigo-900">{dataObj.paper_method || '未知模式'}</h3>
                                <div className="px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-full">已捕获多维阵列</div>
                              </div>
                              <div className="grid grid-cols-2 gap-4 mt-2">
                                <div className="p-3 bg-neutral-50 rounded-lg">
                                  <span className="block text-[10px] text-neutral-400 uppercase font-bold mb-1">DATASETS</span>
                                  <span className="text-sm font-medium text-neutral-700">{dataObj.datasets || '--'}</span>
                                </div>
                                <div className="p-3 bg-neutral-50 rounded-lg">
                                  <span className="block text-[10px] text-neutral-400 uppercase font-bold mb-1">KEY METRICS</span>
                                  <span className="text-sm font-bold text-indigo-600">{dataObj.key_metrics || '--'}</span>
                                </div>
                                <div className="col-span-2 p-3 bg-red-50/50 border border-red-100 rounded-lg">
                                  <span className="block text-[10px] text-red-400 uppercase font-bold mb-1">LIMITATIONS & DEBATES</span>
                                  <span className="text-sm font-medium text-red-800">{dataObj.limitations || '--'}</span>
                                </div>
                              </div>
                           </motion.div>
                        ))}
                     </div>
                  ) : (
                     <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-neutral-200 rounded-3xl bg-neutral-50/50">
                        <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mb-4">
                           <BarChart3 className="w-8 h-8 text-neutral-300" />
                        </div>
                        <h3 className="text-lg font-bold text-neutral-700">数据情报库待命中</h3>
                        <p className="text-neutral-500 text-sm mt-2">请启动流水线以自动生成定量分析结果。</p>
                     </div>
                  )}
                </motion.div>
            )}

            {activeTab === "critic" && (
               <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4 pb-20">
                  <div className="flex items-start gap-6 mb-10">
                     <div className="p-4 rounded-[24px] bg-red-50 border border-red-100 shadow-sm">
                        <ShieldAlert className="w-8 h-8 text-red-500" />
                     </div>
                     <div>
                        <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">红队学术批判</h1>
                        <p className="text-neutral-500 font-medium">AI 红队律师 — 针对当前综述的潜在盲点、过度假设和争议领域进行深度拷问。</p>
                     </div>
                  </div>

                  {stateValues?.critical_checklist && stateValues.critical_checklist.length > 0 ? (
                     <div className="space-y-4">
                        {stateValues.critical_checklist.map((item: any, idx: number) => {
                           const severityConfig: Record<string, {bg: string, border: string, text: string, badge: string, badgeText: string}> = {
                              high:   { bg: 'bg-red-50/80',    border: 'border-red-200',    text: 'text-red-900',    badge: 'bg-red-100 text-red-700',    badgeText: '高风险' },
                              medium: { bg: 'bg-amber-50/80',  border: 'border-amber-200',  text: 'text-amber-900',  badge: 'bg-amber-100 text-amber-700', badgeText: '中风险' },
                              low:    { bg: 'bg-emerald-50/80',border: 'border-emerald-200',text: 'text-emerald-900',badge: 'bg-emerald-100 text-emerald-700', badgeText: '低风险' },
                           };
                           const cfg = severityConfig[item.severity] || severityConfig.medium;
                           return (
                              <motion.div key={idx} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.08 }}
                                 className={`group relative ${cfg.bg} border ${cfg.border} rounded-2xl p-6 shadow-sm hover:shadow-md transition-all`}>
                                 <div className="flex items-start gap-4">
                                    <div className="p-2 rounded-lg bg-white/60 border border-white/80 shadow-sm flex-shrink-0">
                                       <AlertTriangle className={`w-5 h-5 ${item.severity === 'high' ? 'text-red-500' : item.severity === 'medium' ? 'text-amber-500' : 'text-emerald-500'}`} />
                                    </div>
                                    <div className="flex-1">
                                       <div className="flex items-center gap-3 mb-2">
                                          <span className={`text-[11px] font-extrabold uppercase tracking-widest px-2 py-0.5 rounded-md ${cfg.badge}`}>{cfg.badgeText}</span>
                                          <span className="text-xs font-semibold text-neutral-500 bg-white/60 border border-neutral-200/60 px-2 py-0.5 rounded-md">{item.category}</span>
                                       </div>
                                       <p className={`text-[15px] font-medium leading-relaxed ${cfg.text}`}>{item.question}</p>
                                       <button onClick={() => { setIsCopilotOpen(true); setCopilotMsg(`就以下问题，请结合我们原始文献为我深度讨论：${item.question}`); }} className="mt-4 flex items-center gap-1.5 text-[12px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors">
                                          <Sparkles className="w-3.5 h-3.5" /> 通过 Copilot 深度探讨这个问题 <ChevronRight className="w-3.5 h-3.5" />
                                       </button>
                                    </div>
                                 </div>
                              </motion.div>
                           );
                        })}
                     </div>
                  ) : (
                     <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-neutral-200 rounded-3xl bg-neutral-50 h-[450px]">
                        <ShieldAlert className="w-12 h-12 text-neutral-300 mb-4" />
                        <h3 className="text-lg font-bold text-neutral-700">红队分析待机中</h3>
                        <p className="text-neutral-500 text-sm mt-2 text-center max-w-[300px]">运行完整流水线后，AI 批判家将在此处揭露综述的知识盲点。</p>
                     </div>
                  )}
               </motion.div>
            )}

            {activeTab === "library" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4 pb-20">
                  <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">核心文献库</h1>
                  <p className="text-neutral-500 mb-12 font-medium">DeepScholar 已为您自主获取并深度解析了以下核心学术资产。</p>
                  
                  {stateValues?.selected_papers && stateValues.selected_papers.length > 0 ? (
                     <div className="grid grid-cols-2 gap-6">
                        {stateValues.selected_papers.map((paper:any, idx:number) => (
                           <motion.div 
                             initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: idx * 0.05 }}
                             key={idx} className="group relative bg-white/60 backdrop-blur-xl p-6 rounded-3xl border border-white/40 shadow-[0_8px_30px_rgb(0,0,0,0.06)] hover:-translate-y-1 hover:shadow-xl transition-all duration-300 pointer-events-auto">
                              <div className="absolute inset-0 bg-gradient-to-br from-indigo-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-3xl pointer-events-none" />
                              <div className="relative z-10">
                                <div className="flex justify-between items-start mb-3">
                                   <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold bg-neutral-100 text-neutral-600">
                                     {paper.year || 'N/A'}
                                   </span>
                                   <span className="flex items-center text-xs font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md">
                                     Citations: {paper.citation_count || 0}
                                   </span>
                                </div>
                                <h3 className="text-base font-bold text-neutral-800 leading-snug mb-3 line-clamp-2" title={paper.title}>{paper.title}</h3>
                                <p className="text-xs text-neutral-500 line-clamp-3 leading-relaxed mb-4">{paper.abstract}</p>
                                <div className="flex justify-between items-center text-xs text-indigo-600 font-semibold border-t border-neutral-100 pt-4 mt-auto">
                                    <span className="truncate max-w-[200px]">ID: {paper.paper_id}</span>
                                    {paper.pdf_url && <a href={paper.pdf_url} target="_blank" rel="noreferrer" className="flex items-center hover:bg-indigo-50 px-2 py-1 rounded transition-colors"><Download className="w-3 h-3 mr-1"/> PDF</a>}
                                </div>
                              </div>
                           </motion.div>
                        ))}
                     </div>
                  ) : (
                     <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-neutral-200 rounded-[32px] bg-neutral-50/50">
                        <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mb-4 border border-neutral-100">
                           <Library className="w-8 h-8 text-neutral-300" />
                        </div>
                        <h3 className="text-lg font-bold text-neutral-700">文献资产库待命中</h3>
                        <p className="text-neutral-500 text-sm mt-2 font-medium">启动研究流水线后，AI 将在此展示自动精选的高价值文献。</p>
                     </div>
                  )}
                </motion.div>
            )}

            {activeTab === "manuscript" && (
               <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-4 pb-24 h-full relative">
                  <div className="flex justify-between items-end mb-8">
                     <div>
                        <h1 className="text-3xl font-extrabold text-neutral-900 tracking-tight mb-2">综述合成工坊</h1>
                        <p className="text-neutral-500 font-medium font-serif">DeepScholar — 深度合成、严谨引注、符合学术规范的综述文本。</p>
                     </div>
                     <div className="flex gap-3">
                      <div className="flex gap-3">
                         {stateValues?.draft && (
                            <div className="flex gap-2">
                               <button onClick={()=> { const blob=new Blob([stateValues.draft], {type:"text/markdown"}); const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download="synthesis.md"; a.click();}} 
                                   className="px-4 py-2 bg-white border border-neutral-200 hover:border-indigo-500 text-neutral-600 rounded-xl text-xs font-bold shadow-sm transition-all flex items-center">
                                   <Download className="w-3.5 h-3.5 mr-2" /> Markdown
                               </button>
                               <button className="px-4 py-2 bg-white border border-neutral-200 hover:border-indigo-500 text-neutral-400 rounded-xl text-xs font-bold shadow-sm transition-all flex items-center cursor-not-allowed">
                                   <Code className="w-3.5 h-3.5 mr-2 text-neutral-300" /> LaTeX (.zip)
                               </button>
                            </div>
                         )}
                         <button onClick={()=>setIsCopilotOpen(true)} className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-xl shadow-indigo-600/30 transition-all flex items-center">
                            <Sparkles className="w-4 h-4 mr-2" /> Academic Copilot
                         </button>
                      </div>
                   </div>
                </div>
                  
                  {stateValues?.draft ? (
                     <div className="flex gap-8 items-start">
                         {/* Main Manuscript */}
                         <div className="flex-1 bg-white rounded-[24px] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-neutral-200/60 overflow-hidden">
                            <div className="bg-neutral-50/80 px-8 py-4 border-b border-neutral-100 flex items-center gap-4">
                               <div className="flex gap-1.5">
                                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                                  <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                                  <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
                               </div>
                               <span className="text-xs font-semibold text-neutral-400 uppercase tracking-widest pl-2">untitled_synthesis.md</span>
                            </div>
                        
                        {/* Notch/Paper Area */}
                        <div onMouseUp={handleTextSelection} className="p-12 lg:p-20 font-serif text-lg leading-[2.1] text-gray-800 prose prose-lg prose-indigo max-w-none prose-headings:font-sans prose-headings:font-bold prose-headings:tracking-tight prose-h1:text-4xl prose-h2:text-2xl prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-3 prose-h2:mt-10 prose-h3:text-xl prose-a:text-indigo-600 relative">
                             {/* Floating Tooltip selection */}
                             <AnimatePresence>
                               {quoteTooltip && (
                                 <motion.div 
                                    initial={{opacity: 0, y: 10, scale:0.9}} animate={{opacity: 1, y: 0, scale:1}} exit={{opacity: 0, scale:0.95}}
                                    style={{position:'fixed', left: quoteTooltip.x, top: quoteTooltip.y, transform:'translate(-50%, -100%)'}} 
                                    className="z-[999]"
                                 >
                                    <button onMouseDown={(e)=>{e.preventDefault(); askAboutQuote();}} className="flex items-center gap-2 px-4 py-2 bg-[#202020] hover:bg-black text-white text-[13px] font-bold tracking-wide rounded-xl shadow-[0_10px_25px_rgba(0,0,0,0.2)] border border-white/20 transition-all cursor-pointer">
                                       <Sparkles className="w-4 h-4 text-amber-300" />
                                       Ask Copilot
                                    </button>
                                 </motion.div>
                               )}
                             </AnimatePresence>
                             <ReactMarkdown
                               remarkPlugins={[remarkGfm]}
                               components={{
                                 a: ({ href, title, children }) => {
                                   if (href === "#" && title) {
                                     return (
                                       <span className="group relative inline-flex items-center px-2 py-0.5 mx-1 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-md cursor-pointer hover:bg-indigo-100 transition-colors">
                                         <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                                         Ref: {children}
                                         <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-4 bg-gray-900/95 backdrop-blur-sm text-white text-[13px] rounded-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-[999] shadow-2xl shadow-indigo-900/20 text-left font-sans font-normal leading-relaxed pointer-events-none border border-white/10 before:absolute before:top-full before:left-1/2 before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-gray-900/95">
                                           "{title.replace(/&quot;/g, '"')}"
                                         </span>
                                       </span>
                                     );
                                   }
                                   return <a href={href} title={title} className="text-indigo-600 font-semibold hover:underline decoration-indigo-300 underline-offset-4">{children}</a>;
                                 },
                                 table: ({ node, ...props }) => <div className="overflow-x-auto my-10 rounded-2xl border border-neutral-200 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)]"><table className="w-full text-left text-[15px] font-sans m-0" {...props} /></div>,
                                 th: ({ node, ...props }) => <th className="bg-neutral-50/80 font-extrabold text-neutral-700 p-4 border-b border-neutral-200 uppercase tracking-widest text-xs" {...props} />,
                                 td: ({ node, ...props }) => <td className="p-4 border-b border-neutral-100 align-top leading-relaxed text-neutral-600 hover:bg-neutral-50/50 transition-colors" {...props} />,
                                 blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-indigo-500 bg-indigo-50/50 py-2 pr-4 pl-6 text-indigo-900 italic rounded-r-xl my-6" {...props} />
                               }}
                             >
                               {preprocessDraftForMarkdown(stateValues.draft)}
                             </ReactMarkdown>
                        </div>
                    </div>
                         
                         {/* Sidebar Jargon Box (If Available) */}
                         {stateValues?.jargon_dictionary && stateValues.jargon_dictionary.length > 0 && (
                            <div className="w-[300px] shrink-0 sticky top-10 space-y-4">
                               <div className="flex items-center gap-2 px-2 pb-2">
                                  <BookOpen className="w-4 h-4 text-indigo-600" />
                                  <h3 className="font-extrabold text-sm uppercase tracking-widest text-neutral-800">术语百科 / Jargon Buster</h3>
                               </div>
                               {stateValues.jargon_dictionary.map((j:any, i:number) => (
                                   <div onClick={()=>askAboutJargon(j.term)} key={i} className="group cursor-pointer bg-white/90 backdrop-blur-md border border-neutral-200 shadow-sm p-5 rounded-[20px] hover:shadow-[0_15px_30px_rgba(0,0,0,0.06)] hover:border-indigo-300 transition-all hover:-translate-y-1 relative overflow-hidden">
                                       <div className="absolute inset-0 bg-gradient-to-br from-indigo-50/0 to-indigo-50/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                                       <div className="relative z-10">
                                         <div className="font-black text-indigo-700 text-[15px] mb-2 flex items-center justify-between">
                                            {j.term} 
                                            <Sparkles className="w-3.5 h-3.5 text-indigo-400 opacity-0 group-hover:opacity-100 group-hover:animate-pulse transition-opacity" />
                                         </div>
                                         <div className="text-[13px] text-neutral-600 leading-relaxed font-medium line-clamp-3">{j.definition}</div>
                                         <div className="text-[10px] text-indigo-500 font-bold uppercase tracking-widest mt-3 opacity-0 group-hover:opacity-100 transition-opacity">Click to deep dive →</div>
                                       </div>
                                   </div>
                               ))}
                            </div>
                         )}
                     </div>
                  ) : (
                     <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-neutral-200 rounded-3xl bg-neutral-50 h-[500px]">
                         <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mb-4 border border-neutral-100">
                            <FileText className="w-8 h-8 text-neutral-300" />
                         </div>
                         <h3 className="text-lg font-bold text-neutral-700">综述稿件合成中</h3>
                         <p className="text-neutral-500 text-sm mt-2 font-medium">初始草稿组装完成后，编辑器将自动解锁并渲染内容。</p>
                     </div>
                  )}

                  {/* Ultimate Academic Copilot Panel */}
                  <AnimatePresence>
                     {isCopilotOpen && (
                        <>
                           <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} onClick={()=>setIsCopilotOpen(false)} className="fixed inset-0 bg-neutral-900/40 backdrop-blur-sm z-[90]" />
                           <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }} 
                            className="fixed top-0 right-0 h-screen w-[480px] bg-white z-[100] shadow-2xl flex flex-col border-l border-neutral-200">
                              <div className="p-6 border-b border-indigo-500/20 flex justify-between items-center bg-gradient-to-r from-indigo-700 to-indigo-500">
                                  <h2 className="text-white font-extrabold tracking-wide flex items-center gap-3"><Sparkles className="w-5 h-5 text-indigo-200" /> 学术 AI 导师 / Academic Copilot</h2>
                                 <button onClick={()=>setIsCopilotOpen(false)} className="text-indigo-200 hover:text-white transition-colors bg-white/10 p-2 rounded-lg hover:bg-white/20"><X className="w-5 h-5" /></button>
                              </div>
                              
                              <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#FAFAFA]">
                                 {copilotHistory.map((msg, idx) => (
                                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                       <div className={`p-4 rounded-[20px] max-w-[85%] text-[15px] leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-white border border-neutral-200 text-neutral-800 rounded-bl-none'}`}>
                                          {msg.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm prose-indigo leading-relaxed">{msg.content}</ReactMarkdown> : msg.content}
                                       </div>
                                    </div>
                                 ))}
                                 {copilotHistory.length === 0 && (
                                    <div className="text-center text-neutral-400 mt-32">
                                       <div className="w-20 h-20 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                          <Sparkles className="w-10 h-10 text-indigo-300" />
                                       </div>
                                       <p className="font-bold text-neutral-600 mb-2">Welcome to DeepScholar Copilot</p>
                                       <p className="font-medium text-[13px] leading-relaxed">Ask anything about the synthesis.<br/>E.g. <span className="text-indigo-500 cursor-pointer">"Explain this to me like I'm 5"</span></p>
                                    </div>
                                 )}
                              </div>
                              
                              <div className="p-5 bg-white border-t border-neutral-100 shadow-[0_-10px_40px_rgb(0,0,0,0.03)]">
                                 <div className="relative flex shadow-sm rounded-2xl border border-neutral-200 overflow-hidden focus-within:ring-2 focus-within:ring-indigo-500/30 focus-within:border-indigo-500 transition-all">
                                    <input type="text" value={copilotMsg} onChange={e=>setCopilotMsg(e.target.value)} onKeyDown={e=>e.key==='Enter' && onAskCopilot()} placeholder="Ask something..." className="w-full bg-neutral-50 border-none py-4 pl-5 pr-14 text-[15px] outline-none" />
                                    <button onClick={onAskCopilot} className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 hover:scale-105 transition-all"><Send className="w-4 h-4" /></button>
                                 </div>
                              </div>
                           </motion.div>
                        </>
                     )}
                  </AnimatePresence>
               </motion.div>
            )}

         </div>
      </main>
      </div>

      <style>{`
         .custom-scrollbar::-webkit-scrollbar { width: 8px; }
         .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
         .custom-scrollbar::-webkit-scrollbar-thumb { background: #E5E5E5; border-radius: 4px; border: 2px solid #FAFAFA; }
         .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #D4D4D4; }
         
         .bg-noise {
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
            opacity: 0.025;
            pointer-events: none;
         }
      `}</style>
    </div>
  );
}
