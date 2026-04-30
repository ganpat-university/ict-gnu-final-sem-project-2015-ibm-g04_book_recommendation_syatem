"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

type Book = { book_id: number; title?: string; author?: string; score?: number; reason?: string };

export default function HomePage() {
  const [items, setItems] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://13.204.232.136:5000/api/v1/recommend?user_id=1&top_k=12")
      .then((r) => r.json())
      .then((d) => setItems(d.items || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">NovelNest</h1>
        <p className="text-slate-400">Because you liked X • Trending now • Continue reading</p>
      </header>
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-2xl bg-slate-800/70 h-52 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {items.map((b) => (
            <motion.article key={b.book_id} whileHover={{ y: -6 }} className="rounded-2xl border border-slate-700 bg-slate-900/80 p-3">
              <div className="h-32 rounded-xl bg-slate-800 mb-3" />
              <h2 className="text-sm font-semibold line-clamp-2">{b.title || `Book #${b.book_id}`}</h2>
              <p className="text-xs text-slate-400">{b.author || "Unknown Author"}</p>
              <p className="text-xs text-sky-300 mt-1">{b.reason || "hybrid recommendation"}</p>
            </motion.article>
          ))}
        </div>
      )}
    </main>
  );
}
