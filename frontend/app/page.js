const card={background:'white',padding:20,borderRadius:12,border:'1px solid #e5e7eb'};
export default function Home(){return <main style={{maxWidth:1000,margin:'40px auto',padding:20}}>
<h1>AI-Assisted Swing Trading Lab — India</h1>
<p>Experiment mode · ₹1,000 live capital · 1 max live position · human approval required</p>
<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:16}}>
<div style={card}><h3>LIVE</h3><p>Only setups affordable within ₹1,000 and within predefined rupee risk.</p></div>
<div style={card}><h3>SHADOW / PAPER</h3><p>Valid high-quality setups that cannot fit the small live account.</p></div>
<div style={card}><h3>NO TRADE</h3><p>Weak score, bearish regime, poor R:R, event risk, illiquidity, or overextended breakout.</p></div>
</div>
<h2 style={{marginTop:32}}>V1 workflow</h2>
<pre style={{...card,overflow:'auto'}}>Market data → Scanner → Score → Risk engine → LIVE/PAPER → Human approval → Journal → Review</pre>
</main>}
