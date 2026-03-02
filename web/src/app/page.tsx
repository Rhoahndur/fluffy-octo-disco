'use client';

import { useState, useCallback, ChangeEvent } from 'react';
import type { EstimateResponse, DivisionBreakdown } from '@/types';
import type { ImageFile } from '@/lib/utils/image';
import { validateImageFile, compressImage, fileToBase64 } from '@/lib/utils/image';

export default function Home() {
  const [view, setView] = useState<'landing' | 'dashboard' | 'results'>('landing');

  // Dashboard State
  const [images, setImages] = useState<ImageFile[]>([]);
  const [projectName, setProjectName] = useState('');
  const [sqFootage, setSqFootage] = useState('');
  const [stories, setStories] = useState('');
  const [location, setLocation] = useState('New York, NY');
  const [buildingType, setBuildingType] = useState('Commercial');
  const [description, setDescription] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Results State
  const [estimateResponse, setEstimateResponse] = useState<EstimateResponse | null>(null);

  const handleFileSelect = useCallback(async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setError(null);
    const newImages: ImageFile[] = [];
    const fileArray = Array.from(files);

    const maxImages = 10;
    const remaining = maxImages - images.length;
    if (fileArray.length > remaining) {
      setError(`Can only add ${remaining} more image(s). Max ${maxImages} total.`);
      fileArray.splice(remaining);
    }

    for (const file of fileArray) {
      const validation = validateImageFile(file);
      if (!validation.valid) {
        setError(validation.error || 'Invalid file');
        continue;
      }

      try {
        const compressed = await compressImage(file, 1);
        const preview = URL.createObjectURL(compressed);
        const base64 = await fileToBase64(compressed);

        newImages.push({
          file: compressed,
          preview,
          base64,
        });
      } catch (err) {
        console.error('Failed to process image:', err);
        setError('Failed to process image');
      }
    }

    setImages((prev) => [...prev, ...newImages]);
    e.target.value = '';
  }, [images.length]);

  const removeImage = (index: number) => {
    setImages((prev) => {
      const newImages = [...prev];
      URL.revokeObjectURL(newImages[index].preview);
      newImages.splice(index, 1);
      return newImages;
    });
  };

  const handleGenerateEstimate = async () => {
    if (images.length === 0 && description.trim().length === 0) {
      setError('Please upload at least one image or provide a project description.');
      return;
    }

    setLoading(true);
    setError(null);

    // Combine form data into description if provided to enrich the prompt
    let fullDescription = description;
    const details = [];
    if (projectName) details.push(`Project Name: ${projectName}`);
    if (sqFootage) details.push(`Square Footage: ${sqFootage} sq ft`);
    if (stories) details.push(`Stories: ${stories}`);
    if (buildingType) details.push(`Building Type: ${buildingType}`);

    if (details.length > 0) {
      fullDescription = `${details.join('\n')}\n\nNotes:\n${fullDescription}`;
    }

    try {
      const response = await fetch('/api/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: images.map((img) => img.base64),
          description: fullDescription.trim(),
          location: location.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to generate estimate');
      }

      const result: EstimateResponse = await response.json();
      setEstimateResponse(result);
      setView('results');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleNewEstimate = () => {
    setImages([]);
    setProjectName('');
    setSqFootage('');
    setStories('');
    setDescription('');
    setEstimateResponse(null);
    setError(null);
    setView('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Helper to safely format currency
  const formatCurrency = (value?: number) => {
    if (value === undefined || value === null || isNaN(value)) return '$0';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  };

  // Safe mapping of CSI names
  const divisionNames: Record<string, string> = {
    '01_general_requirements': 'General Requirements',
    '02_existing_conditions': 'Existing Conditions',
    '03_concrete': 'Concrete',
    '04_masonry': 'Masonry',
    '05_metals': 'Metals',
    '06_wood_plastics_composites': 'Wood & Plastics',
    '07_thermal_moisture': 'Thermal & Moisture',
    '08_openings': 'Openings',
    '09_finishes': 'Finishes',
    '10_specialties': 'Specialties',
    '11_equipment': 'Equipment',
    '12_furnishings': 'Furnishings',
    '13_special_construction': 'Special Construction',
    '14_conveying_equipment': 'Conveying Equipment',
    '21_fire_suppression': 'Fire Suppression',
    '22_plumbing': 'Plumbing',
    '23_hvac': 'HVAC',
    '26_electrical': 'Electrical',
  };

  // Convert breakdown object to sorted array safely
  const getSortedDivisions = (breakdown?: DivisionBreakdown, totalCost?: number) => {
    if (!breakdown || !totalCost || totalCost === 0) return [];

    return Object.entries(breakdown)
      .map(([key, cost]) => {
        const divNumberStr = key.split('_')[0];
        const percent = (cost / totalCost) * 100;
        return {
          id: key,
          number: divNumberStr,
          name: divisionNames[key] || key.replace(/_/g, ' '),
          cost,
          percent
        };
      })
      .filter(item => item.cost > 0)
      .sort((a, b) => b.cost - a.cost);
  };

  return (
    <div className="relative flex h-auto min-h-screen w-full flex-col">
      {/* ==================== HEADER ==================== */}
      <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-[#0A0A0A]/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-8">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => { setView('landing'); window.scrollTo(0, 0); }}>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
              <span className="material-symbols-outlined text-[24px]">architecture</span>
            </div>
            <span className="text-xl font-bold tracking-tight text-white">SiteScope</span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            <a className="text-sm font-medium text-slate-300 hover:text-white transition-colors" href="#" onClick={(e) => { e.preventDefault(); setView('landing'); }}>Features</a>
            <a className="text-sm font-medium text-slate-300 hover:text-white transition-colors" href="#" onClick={(e) => { e.preventDefault(); setView('landing'); }}>How It Works</a>
            <a className="text-sm font-medium text-slate-300 hover:text-white transition-colors" href="#" onClick={(e) => { e.preventDefault(); setView('dashboard'); }}>Dashboard</a>
          </nav>
          <div className="flex items-center gap-4">
            <button className="hidden md:flex h-9 items-center justify-center rounded-lg border border-white/10 px-4 text-sm font-medium text-white hover:bg-white/5 transition-colors">Log In</button>
            <button onClick={() => setView('dashboard')} className="flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-bold text-white shadow-glow shadow-primary/50 hover:bg-primary/90 transition-all">Get Started</button>
          </div>
        </div>
      </header>

      {/* ==================== LANDING PAGE ==================== */}
      {view === 'landing' && (
        <main className="flex-col flex-grow animate-fade-in-up">
          <section className="relative isolate overflow-hidden pt-14 lg:pt-24 pb-20">
            <div className="absolute inset-0 -z-20 bg-blueprint-grid bg-grid-pattern opacity-30"></div>
            <div aria-hidden="true" className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-80">
              <div className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-primary to-[#9089fc] opacity-20 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]"></div>
            </div>
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
              <div className="mx-auto max-w-3xl text-center">
                <div className="mb-6 flex justify-center">
                  <div className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary backdrop-blur-sm">New: RSMeans 2024 Data Integration</div>
                </div>
                <h1 className="text-4xl font-black tracking-tight text-white sm:text-6xl lg:text-7xl">
                  Construction Cost <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-blue-400 to-indigo-400">Estimates in Seconds.</span>
                </h1>
                <p className="mt-6 text-lg leading-8 text-slate-400 max-w-2xl mx-auto">
                  AI analysis powered by <span className="text-white font-medium">Claude &amp; Gemini</span>, calibrated with <span className="text-white font-medium">RSMeans</span> for precision breakdowns. Turn blueprints into budgets instantly.
                </p>
                <div className="mt-10 flex items-center justify-center gap-x-6">
                  <button onClick={() => setView('dashboard')} className="group flex h-12 items-center gap-2 rounded-lg bg-primary px-8 text-base font-bold text-white shadow-lg shadow-primary/25 transition-all hover:scale-105 hover:bg-primary/90">
                    Start Estimating
                    <span className="material-symbols-outlined text-[20px] transition-transform group-hover:translate-x-1">arrow_forward</span>
                  </button>
                </div>
                <div className="mt-14 pt-8 border-t border-white/5">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-6">Powered by industry leaders</p>
                  <div className="flex justify-center items-center gap-8 opacity-60 grayscale hover:grayscale-0 transition-all duration-500 flex-wrap">
                    <div className="flex items-center gap-2"><span className="material-symbols-outlined text-3xl">psychology</span><span className="font-bold text-xl">Claude AI</span></div>
                    <div className="hidden sm:block h-4 w-px bg-white/20"></div>
                    <div className="flex items-center gap-2"><span className="material-symbols-outlined text-3xl">auto_awesome</span><span className="font-bold text-xl">Gemini</span></div>
                    <div className="hidden sm:block h-4 w-px bg-white/20"></div>
                    <div className="flex items-center gap-2"><span className="material-symbols-outlined text-3xl">analytics</span><span className="font-bold text-xl">RSMeans</span></div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="bg-[#111418]/50 border-y border-white/5 py-12 relative overflow-hidden">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
              <dl className="grid grid-cols-1 gap-x-8 gap-y-8 text-center lg:grid-cols-3">
                <div className="mx-auto flex max-w-xs flex-col gap-y-2">
                  <dt className="text-base leading-7 text-slate-400">Projects Estimated</dt>
                  <dd className="order-first text-3xl font-bold tracking-tight text-white sm:text-5xl">2,400+</dd>
                </div>
                <div className="mx-auto flex max-w-xs flex-col gap-y-2">
                  <dt className="text-base leading-7 text-slate-400">Construction Value</dt>
                  <dd className="order-first text-3xl font-bold tracking-tight text-primary sm:text-5xl">$1.2B+</dd>
                </div>
                <div className="mx-auto flex max-w-xs flex-col gap-y-2">
                  <dt className="text-base leading-7 text-slate-400">Accuracy Rate</dt>
                  <dd className="order-first text-3xl font-bold tracking-tight text-white sm:text-5xl">92%</dd>
                </div>
              </dl>
            </div>
          </section>

          <section className="py-24 sm:py-32 bg-[#111418] relative">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
              <div className="mx-auto max-w-2xl text-center mb-16">
                <h2 className="text-primary font-semibold tracking-wide uppercase text-sm">Capabilities</h2>
                <p className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">Premium Estimation Features</p>
                <p className="mt-4 text-lg text-slate-400">Leverage the power of multiple AI models and industry-standard data to ensure your bids are accurate and competitive.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="glass-card rounded-xl p-8 hover:border-primary/50 transition-colors group relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity"><span className="material-symbols-outlined text-8xl text-primary">memory</span></div>
                  <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform"><span className="material-symbols-outlined text-2xl">memory</span></div>
                  <h3 className="text-xl font-bold text-white mb-3">Multi-AI Analysis</h3>
                  <p className="text-slate-400 leading-relaxed">Cross-referenced analysis using both Claude and Gemini models to detect potential cost overruns and material conflicts.</p>
                </div>
                <div className="glass-card rounded-xl p-8 hover:border-primary/50 transition-colors group relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity"><span className="material-symbols-outlined text-8xl text-primary">attach_money</span></div>
                  <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform"><span className="material-symbols-outlined text-2xl">attach_money</span></div>
                  <h3 className="text-xl font-bold text-white mb-3">RSMeans Calibrated</h3>
                  <p className="text-slate-400 leading-relaxed">Real-time calibration with RSMeans location factors ensures your labor and material costs are accurate for your specific zip code.</p>
                </div>
                <div className="glass-card rounded-xl p-8 hover:border-primary/50 transition-colors group relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity"><span className="material-symbols-outlined text-8xl text-primary">format_list_numbered</span></div>
                  <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform"><span className="material-symbols-outlined text-2xl">format_list_numbered</span></div>
                  <h3 className="text-xl font-bold text-white mb-3">18 CSI Divisions</h3>
                  <p className="text-slate-400 leading-relaxed">Automatically structures your estimates into the 18 standard CSI MasterFormat divisions for immediate professional presentation.</p>
                </div>
              </div>
            </div>
          </section>

          <footer className="bg-[#111418] border-t border-white/5 pt-16 pb-8">
            <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center text-slate-500 text-sm">
              &copy; 2026 SiteScope Inc. All rights reserved.
            </div>
          </footer>
        </main>
      )}

      {/* ==================== DASHBOARD VIEW ==================== */}
      {view === 'dashboard' && (
        <main className="flex-col flex-grow flex animate-fade-in-up">
          <div className="flex-1 flex flex-col md:flex-row min-h-[calc(100vh-64px)]">
            <div className="w-full md:w-[45%] min-w-[320px] max-w-[600px] flex flex-col border-r border-[#2d3b45] bg-[#111418] overflow-y-auto">
              <div className="p-6 md:p-8 flex flex-col gap-6">
                <div className="space-y-1">
                  <h1 className="text-2xl font-bold text-white tracking-tight">Project Details</h1>
                  <p className="text-slate-400 text-sm">Enter the specifications for your construction estimate.</p>
                </div>

                <div className="glass-card rounded-xl p-6 flex flex-col gap-5">
                  {/* File Upload Area */}
                  <div className="relative group cursor-pointer">
                    <input
                      className="absolute inset-0 w-full h-full opacity-0 z-10 cursor-pointer"
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      onChange={handleFileSelect}
                      disabled={loading}
                    />
                    <div className={`border-2 border-dashed ${images.length > 0 ? 'border-primary/50 bg-primary/5' : 'border-slate-600'} group-hover:border-primary/50 group-hover:bg-primary/5 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all bg-[#0A0A0A]`}>
                      <div className="size-12 rounded-full bg-[#111418] border border-[#2d3b45] flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                        <span className="material-symbols-outlined text-primary text-2xl">cloud_upload</span>
                      </div>
                      <p className="text-white font-medium mb-1">
                        {images.length > 0 ? `${images.length} blueprints uploaded` : 'Upload Blueprints'}
                      </p>
                      <p className="text-xs text-slate-400">PDF, PNG, JPG up to 50MB</p>
                    </div>
                  </div>

                  {/* Image Previews */}
                  {images.length > 0 && (
                    <div className="flex gap-2 overflow-x-auto pb-2">
                      {images.map((img, idx) => (
                        <div key={idx} className="relative flex-none w-20 h-20 rounded-md overflow-hidden border border-slate-700 group">
                          <img src={img.preview} className="w-full h-full object-cover" alt="Preview" />
                          <button onClick={() => removeImage(idx)} className="absolute top-1 right-1 bg-red-500 text-white rounded-full size-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                            <span className="material-symbols-outlined text-[14px]">close</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-1 gap-5">
                    <label className="flex flex-col gap-2">
                      <span className="text-slate-300 text-sm font-medium">Project Name</span>
                      <input value={projectName} onChange={e => setProjectName(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-2.5 text-white placeholder:text-slate-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm" placeholder="e.g. Riverside Office Complex" type="text" />
                    </label>

                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex flex-col gap-2">
                        <span className="text-slate-300 text-sm font-medium">Sq. Footage</span>
                        <div className="relative">
                          <input value={sqFootage} onChange={e => setSqFootage(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-2.5 text-white placeholder:text-slate-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm" placeholder="20,000" type="number" />
                          <span className="absolute right-3 top-2.5 text-slate-500 text-xs font-medium">ft²</span>
                        </div>
                      </label>
                      <label className="flex flex-col gap-2">
                        <span className="text-slate-300 text-sm font-medium">Stories</span>
                        <input value={stories} onChange={e => setStories(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-2.5 text-white placeholder:text-slate-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm" placeholder="8" type="number" />
                      </label>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex flex-col gap-2">
                        <span className="text-slate-300 text-sm font-medium">Location</span>
                        <div className="relative">
                          <select value={location} onChange={e => setLocation(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-2.5 text-white appearance-none focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm">
                            <option>New York, NY</option>
                            <option>Los Angeles, CA</option>
                            <option>Chicago, IL</option>
                            <option>Houston, TX</option>
                            <option>Austin, TX</option>
                            <option>Miami, FL</option>
                          </select>
                          <span className="material-symbols-outlined absolute right-3 top-2.5 text-slate-500 text-lg pointer-events-none">expand_more</span>
                        </div>
                      </label>
                      <label className="flex flex-col gap-2">
                        <span className="text-slate-300 text-sm font-medium">Building Type</span>
                        <div className="relative">
                          <select value={buildingType} onChange={e => setBuildingType(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-2.5 text-white appearance-none focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm">
                            <option>Commercial</option>
                            <option>Residential</option>
                            <option>Industrial</option>
                            <option>Institutional</option>
                            <option>Infrastructure</option>
                          </select>
                          <span className="material-symbols-outlined absolute right-3 top-2.5 text-slate-500 text-lg pointer-events-none">expand_more</span>
                        </div>
                      </label>
                    </div>

                    <label className="flex flex-col gap-2">
                      <span className="text-slate-300 text-sm font-medium">Description</span>
                      <textarea value={description} onChange={e => setDescription(e.target.value)} disabled={loading} className="w-full bg-[#0A0A0A] border border-[#2d3b45] rounded-lg px-4 py-3 text-white placeholder:text-slate-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm min-h-[100px] resize-none" placeholder="Describe your project scope, materials, and any special requirements..."></textarea>
                    </label>
                  </div>

                  {error && (
                    <div className="p-3 rounded border border-red-500/50 bg-red-500/10 text-red-400 text-sm mt-2">
                      {error}
                    </div>
                  )}

                  <div className="mt-2">
                    <button
                      onClick={handleGenerateEstimate}
                      disabled={loading || (images.length === 0 && description.length === 0)}
                      className="w-full h-12 flex items-center justify-center gap-2 rounded-lg bg-primary text-white font-bold shadow-glow shadow-primary/40 hover:shadow-[0_0_30px_-5px_rgba(60,131,246,0.6)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none"
                    >
                      {loading ? (
                        <>
                          <span className="material-symbols-outlined text-lg animate-spin">progress_activity</span>
                          <span>AI Analysis in Progress...</span>
                        </>
                      ) : (
                        <>
                          <span>Generate Estimate</span>
                          <span className="material-symbols-outlined text-lg">arrow_forward</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="hidden md:flex flex-1 bg-[#0A0A0A] relative items-center justify-center p-8 overflow-hidden">
              <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#3c83f6 1px, transparent 1px)', backgroundSize: '30px 30px' }}></div>
              <div className="max-w-md w-full text-center relative z-10 flex flex-col items-center">
                <div className="relative w-64 h-64 mb-8">
                  <div className="absolute inset-0 border border-slate-700/50 rounded-full animate-[spin_10s_linear_infinite]"></div>
                  <div className="absolute inset-4 border border-dashed border-slate-700/50 rounded-full animate-[spin_15s_linear_infinite_reverse]"></div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="size-32 bg-[#111418]/80 backdrop-blur rounded-xl border border-[#2d3b45] flex items-center justify-center shadow-2xl relative overflow-hidden text-slate-500">
                      {loading ? <span className="material-symbols-outlined text-6xl text-primary animate-pulse">memory</span> : <span className="material-symbols-outlined text-6xl">grid_on</span>}
                    </div>
                  </div>
                </div>
                {loading ? (
                  <>
                    <h3 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary to-indigo-400 mb-3 animate-pulse">Analyzing Blueprints</h3>
                    <p className="text-slate-400 leading-relaxed max-w-sm mx-auto">Cross-referencing Claude & Gemini models against RSMeans data...</p>
                  </>
                ) : (
                  <>
                    <h3 className="text-2xl font-bold text-white mb-3">Ready to Estimate</h3>
                    <p className="text-slate-400 leading-relaxed max-w-sm mx-auto">Your cost breakdown will appear here. Upload your project documents or fill in the details on the left to get started.</p>
                  </>
                )}
              </div>
            </div>
          </div>
        </main>
      )}

      {/* ==================== RESULTS VIEW ==================== */}
      {view === 'results' && estimateResponse && (
        <main className="flex-col flex-grow animate-fade-in-up">
          <div className="max-w-[1280px] mx-auto w-full px-4 py-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-10 pb-6 border-b border-slate-800">
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-3xl md:text-4xl font-black tracking-tight">{projectName || 'Project Estimate'}</h2>
                  {estimateResponse.analysis?.confidence && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      <span className="material-symbols-outlined text-[14px]">check_circle</span>
                      {(estimateResponse.analysis.confidence * 100).toFixed(0)}% Confidence
                    </span>
                  )}
                </div>
                <p className="text-slate-400 text-sm">Generated on {new Date(estimateResponse.created_at).toLocaleDateString()} &bull; ID: #{estimateResponse.id?.substring(0, 8).toUpperCase()}</p>
              </div>
              <div className="flex items-center gap-3">
                <button className="flex items-center gap-2 h-10 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium transition-colors">
                  <span className="material-symbols-outlined text-[18px]">picture_as_pdf</span>Export
                </button>
                <button onClick={handleNewEstimate} className="flex items-center gap-2 h-10 px-4 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-sm font-medium transition-colors">
                  <span className="material-symbols-outlined text-[18px]">add</span>New
                </button>
              </div>
            </div>

            <div className="mb-10 text-center md:text-left">
              <p className="text-slate-400 font-medium mb-1">Total Estimated Cost</p>
              <div className="text-5xl md:text-7xl font-black tracking-tight text-white text-glow-blue">
                {formatCurrency(estimateResponse.estimate?.total_cost)}
              </div>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 hover:border-primary/30 transition-colors group">
                <div className="flex justify-between items-start"><p className="text-slate-400 text-sm font-medium">Cost per sq ft</p><span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">square_foot</span></div>
                <p className="text-2xl font-bold text-white">{formatCurrency(estimateResponse.estimate?.cost_per_sf)} <span className="text-base font-normal text-slate-500">/ sq ft</span></p>
              </div>
              <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 hover:border-primary/30 transition-colors group">
                <div className="flex justify-between items-start"><p className="text-slate-400 text-sm font-medium">Building Type</p><span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">domain</span></div>
                <p className="text-xl font-bold text-white capitalize">{estimateResponse.analysis?.merged?.building_type || buildingType}</p>
              </div>
              <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 hover:border-primary/30 transition-colors group">
                <div className="flex justify-between items-start"><p className="text-slate-400 text-sm font-medium">Location Factor</p><span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">location_on</span></div>
                <p className="text-2xl font-bold text-white">{estimateResponse.estimate?.location_factor?.toFixed(2) || '1.00'} <span className="text-base font-normal text-slate-500">- {location.split(',')[0]}</span></p>
              </div>
              <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 hover:border-primary/30 transition-colors group">
                <div className="flex justify-between items-start"><p className="text-slate-400 text-sm font-medium">Quality Level</p><span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">hotel_class</span></div>
                <p className="text-xl font-bold text-white capitalize">{estimateResponse.estimate?.quality || 'Mid'}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 flex flex-col gap-6">
                <h3 className="text-xl font-bold text-white">Cost Breakdown by CSI Division</h3>
                <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-sm">
                  <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-slate-800/50 border-b border-slate-800 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <div className="col-span-1">Div</div><div className="col-span-4 lg:col-span-5">Category</div><div className="col-span-3 text-right">Cost</div><div className="col-span-4 lg:col-span-3 pl-4">Percent</div>
                  </div>

                  {getSortedDivisions(estimateResponse.estimate?.division_breakdown, estimateResponse.estimate?.total_cost).map((div, i) => (
                    <div key={div.id} className="grid grid-cols-12 gap-4 px-6 py-4 items-center border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors relative overflow-hidden group">
                      {i < 3 && <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-primary shadow-glow"></div>}
                      <div className="col-span-1 text-slate-400 font-mono text-[13px]">{div.number}</div>
                      <div className="col-span-4 lg:col-span-5 text-slate-200 font-medium text-[13px] sm:text-sm truncate">{div.name}</div>
                      <div className="col-span-3 text-right group-hover:text-white text-slate-300 font-semibold text-sm">{formatCurrency(div.cost)}</div>
                      <div className="col-span-4 lg:col-span-3 pl-4 flex items-center gap-3">
                        <div className="flex-1 h-2 bg-slate-700/50 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${i < 3 ? 'bg-gradient-to-r from-blue-600 to-blue-400 shadow-[0_0_10px_rgba(60,131,246,0.4)]' : 'bg-slate-500'}`} style={{ width: `${Math.max(1, div.percent)}%` }}></div>
                        </div>
                        <span className="text-[11px] text-slate-500 w-8 text-right font-mono">{div.percent.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Analysis Side Panel */}
              <div className="lg:col-span-1 flex flex-col gap-6">
                <h3 className="text-xl font-bold text-white">Analysis Details</h3>
                <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 flex flex-col gap-6 shadow-sm">
                  <div>
                    <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-4">Technical Specs</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/30 border border-slate-800/50">
                        <span className="text-[11px] text-slate-500">Structure</span>
                        <span className="text-sm font-semibold text-slate-200 truncate capitalize">{estimateResponse.analysis?.merged?.construction_type?.replace(/_/g, ' ') || 'Unknown'}</span>
                      </div>
                      <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/30 border border-slate-800/50">
                        <span className="text-[11px] text-slate-500">Stories</span>
                        <span className="text-sm font-semibold text-slate-200">{estimateResponse.analysis?.merged?.stories || stories || '1'}</span>
                      </div>
                      <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/30 border border-slate-800/50">
                        <span className="text-[11px] text-slate-500">Total Area</span>
                        <span className="text-sm font-semibold text-slate-200">{Number(estimateResponse.analysis?.merged?.estimated_sqft || sqFootage).toLocaleString()} sf</span>
                      </div>
                      <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/30 border border-slate-800/50">
                        <span className="text-[11px] text-slate-500">Sub-type</span>
                        <span className="text-sm font-semibold text-slate-200 truncate capitalize">{estimateResponse.analysis?.merged?.sub_type?.replace(/_/g, ' ') || '-'}</span>
                      </div>
                    </div>
                  </div>

                  {estimateResponse.analysis?.merged?.materials_detected && estimateResponse.analysis.merged.materials_detected.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-3">Detected Materials</h4>
                      <div className="flex flex-wrap gap-2">
                        {estimateResponse.analysis.merged.materials_detected.map((mat, i) => (
                          <span key={i} className={`px-2.5 py-1 rounded-md text-[11px] font-medium border ${i < 2 ? 'bg-primary/10 border-primary/20 text-primary' : 'bg-slate-800 border-slate-700 text-slate-300'}`}>
                            {mat}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {estimateResponse.analysis?.conflicts && estimateResponse.analysis.conflicts.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold text-amber-500/80 uppercase tracking-wider mb-3 flex items-center gap-1">
                        <span className="material-symbols-outlined text-[14px]">warning</span> AI Conflicts
                      </h4>
                      <ul className="text-xs text-slate-400 space-y-2 list-disc pl-4">
                        {estimateResponse.analysis.conflicts.map((c, i) => <li key={i}>{c}</li>)}
                      </ul>
                    </div>
                  )}

                  <div className="pt-4 border-t border-slate-800 mt-2">
                    <button onClick={() => setView('dashboard')} className="w-full h-10 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm font-medium transition-colors flex items-center justify-center gap-2">
                      <span className="material-symbols-outlined text-[16px]">edit_document</span>Edit Parameters
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
