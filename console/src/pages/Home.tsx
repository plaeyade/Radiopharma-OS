import { useCallback, useEffect, useState } from "react";
import { Activity, Atom, FlaskConical, LineChart, LogIn, LogOut, Radio, RefreshCw, ScrollText, Settings, User, Waves } from "lucide-react";
import { Toaster, toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchConsole, loadConfig, saveConfig, type ConsoleConfig, type ConsoleData } from "@/lib/console-data";
import { clearSession, loadSession, saveSession, type Session } from "@/lib/session";
import { login } from "@/lib/actions";
import Overview from "@/sections/Overview";
import BatchesSection from "@/sections/BatchesSection";
import QcSection from "@/sections/QcSection";
import EbrSection from "@/sections/EbrSection";
import TelemetrySection from "@/sections/TelemetrySection";
import TrendsSection from "@/sections/TrendsSection";

export default function Home() {
  const [data, setData] = useState<ConsoleData | null>(null);
  const [cfg, setCfg] = useState<ConsoleConfig>(loadConfig());
  const [session, setSession] = useState<Session | null>(loadSession());
  const [loading, setLoading] = useState(false);
  const [batchId, setBatchId] = useState<string>("");
  const [loginOpen, setLoginOpen] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    const eff = { ...cfg, token: session?.token ?? cfg.token };
    const d = await fetchConsole(eff);
    setData(d);
    setBatchId((prev) => prev && d.batches.some((b) => b.batch_id === prev)
      ? prev : d.batches[0]?.batch_id ?? "");
    setLoading(false);
  }, [cfg, session]);

  useEffect(() => { void reload(); }, [session]);  // eslint-disable-line react-hooks/exhaustive-deps

  const doLogin = async (u: string, p: string) => {
    try {
      const token = await login(cfg, u, p);
      const s = saveSession(token);
      setSession(s);
      setLoginOpen(false);
      toast.success(`Sesión iniciada como ${s?.username} (${s?.role})`);
    } catch (e) {
      toast.error(`Login falló: ${(e as Error).message}`);
    }
  };

  const doLogout = () => {
    clearSession();
    setSession(null);
    toast.info("Sesión cerrada");
  };

  const effCfg = { ...cfg, token: session?.token ?? cfg.token };

  return (
    <div className="dark min-h-screen bg-[#0a0f16] text-slate-200">
      <Toaster theme="dark" position="bottom-right" />
      <header className="border-b border-slate-800 bg-[#0d1420]">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-400">
            <Atom className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Radiopharma OS <span className="font-normal text-slate-400">· Consola Operacional</span>
            </h1>
            <p className="text-xs text-slate-500">Physics Twin · Data Lake GMP · Operational Twin</p>
          </div>
          {data && (
            <Badge variant={data.mode === "live" ? "default" : "secondary"}
                   className={data.mode === "live"
                     ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/15"
                     : "bg-amber-500/15 text-amber-400 hover:bg-amber-500/15"}>
              {data.mode === "live" ? "● EN VIVO" : "● DEMOSTRACIÓN"}
            </Badge>
          )}
          {session ? (
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-1.5">
              <User className="h-3.5 w-3.5 text-cyan-400" />
              <span className="text-xs text-slate-300">{session.username}</span>
              <Badge variant="outline" className="border-cyan-800 text-[10px] text-cyan-300">{session.role}</Badge>
              <button onClick={doLogout} title="Cerrar sesión"
                      className="text-slate-500 hover:text-red-400">
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <Dialog open={loginOpen} onOpenChange={setLoginOpen}>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-cyan-600 text-white hover:bg-cyan-500">
                  <LogIn className="mr-1 h-3.5 w-3.5" /> Entrar
                </Button>
              </DialogTrigger>
              <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
                <DialogHeader><DialogTitle>Iniciar sesión (Auth Service)</DialogTitle></DialogHeader>
                <LoginForm onSubmit={doLogin} />
              </DialogContent>
            </Dialog>
          )}
          <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}
                  className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800">
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800">
                <Settings className="h-3.5 w-3.5" />
              </Button>
            </DialogTrigger>
            <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
              <DialogHeader><DialogTitle>Conexión a microservicios</DialogTitle></DialogHeader>
              <p className="text-xs text-slate-400">
                En docker-compose los valores por defecto son prefijos relativos (<code>/auth</code>, <code>/dl</code>…) que nginx proxifica a cada servicio. Para desarrollo usa URLs absolutas (<code>http://localhost:8004</code>, …).
              </p>
              <div className="grid grid-cols-2 gap-3">
                {([
                  ["authUrl", "Auth (/auth)"], ["dlUrl", "Data Lake (/dl)"],
                  ["yeUrl", "Yield Engine (/ye)"], ["ndsUrl", "Nuclear Data (/nds)"],
                  ["qcUrl", "QC Engine (/qc)"], ["telUrl", "Telemetry (/tel)"],
                ] as const).map(([key, label]) => (
                  <div key={key}>
                    <Label>{label}</Label>
                    <Input value={cfg[key]} onChange={(e) => setCfg({ ...cfg, [key]: e.target.value })}
                           className="border-slate-700 bg-slate-900 text-xs" />
                  </div>
                ))}
                <Button className="col-span-2" onClick={() => { saveConfig(cfg); void reload(); }}>
                  Guardar y reconectar
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {!data ? (
          <p className="py-20 text-center text-slate-500">Conectando con los microservicios…</p>
        ) : (
          <Tabs defaultValue="overview">
            <TabsList className="border border-slate-800 bg-[#0d1420]">
              <TabsTrigger value="overview"><Activity className="mr-1.5 h-4 w-4" />Resumen</TabsTrigger>
              <TabsTrigger value="batches"><FlaskConical className="mr-1.5 h-4 w-4" />Lotes</TabsTrigger>
              <TabsTrigger value="qc"><Radio className="mr-1.5 h-4 w-4" />Control de calidad</TabsTrigger>
              <TabsTrigger value="ebr"><ScrollText className="mr-1.5 h-4 w-4" />eBR</TabsTrigger>
              <TabsTrigger value="telemetry"><Waves className="mr-1.5 h-4 w-4" />Telemetría</TabsTrigger>
              <TabsTrigger value="trends"><LineChart className="mr-1.5 h-4 w-4" />Tendencias</TabsTrigger>
            </TabsList>
            <div className="mt-5">
              <TabsContent value="overview">
                <Overview data={data} onSelectBatch={setBatchId} />
              </TabsContent>
              <TabsContent value="batches">
                <BatchesSection data={data} cfg={effCfg} session={session}
                                selected={batchId} onSelect={setBatchId} onChanged={reload} />
              </TabsContent>
              <TabsContent value="qc">
                <QcSection data={data} cfg={effCfg} session={session}
                           selected={batchId} onSelect={setBatchId} onChanged={reload} />
              </TabsContent>
              <TabsContent value="ebr">
                <EbrSection data={data} cfg={effCfg} session={session}
                            selected={batchId} onSelect={setBatchId} onChanged={reload} />
              </TabsContent>
              <TabsContent value="telemetry">
                <TelemetrySection data={data} cfg={effCfg} session={session}
                                  selected={batchId} onSelect={setBatchId} onChanged={reload} />
              </TabsContent>
              <TabsContent value="trends">
                <TrendsSection data={data} />
              </TabsContent>
            </div>
          </Tabs>
        )}
      </main>
      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        Radiopharma OS v0.19.0 · datos nucleares 100 % abiertos (IAEA-NDS · DDEP · CATIMA)
        {data && ` · actualizado ${new Date(data.fetched_at).toLocaleTimeString("es-MX")}`}
      </footer>
    </div>
  );
}

function LoginForm({ onSubmit }: { onSubmit: (u: string, p: string) => void }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onSubmit(u, p); }}>
      <div>
        <Label htmlFor="u">Usuario</Label>
        <Input id="u" value={u} onChange={(e) => setU(e.target.value)}
               className="border-slate-700 bg-slate-900" placeholder="operador.ciclotron" />
      </div>
      <div>
        <Label htmlFor="p">Contraseña</Label>
        <Input id="p" type="password" value={p} onChange={(e) => setP(e.target.value)}
               className="border-slate-700 bg-slate-900" />
      </div>
      <Button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-500">Entrar</Button>
    </form>
  );
}
