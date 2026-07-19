import { useState } from "react";
import { Download, FileCheck2, PenLine } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { signEbr } from "@/lib/actions";
import type { ConsoleConfig, ConsoleData } from "@/lib/console-data";
import { fmtTs, MEANING_ES, shortHash } from "@/lib/format";
import { roleRank, type Session } from "@/lib/session";

const ACCION_ES: Record<string, string> = {
  batch_registered: "Lote registrado",
  qc_report_registered: "Informe QC registrado",
  batch_released: "Lote liberado",
  batch_rejected: "Lote rechazado",
  signature_performed_by: "Firma: realizado por",
  signature_reviewed_by: "Firma: revisado por",
  signature_approved_by: "Firma: aprobado por",
};

const MIN_ROLE: Record<string, number> = { performed_by: 1, reviewed_by: 2, approved_by: 3 };

interface Props {
  data: ConsoleData; cfg: ConsoleConfig; session: Session | null;
  selected: string; onSelect: (id: string) => void; onChanged: () => void;
}

export default function EbrSection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const batch = data.batches.find((x) => x.batch_id === selected) ?? data.batches[0];
  const doc = batch ? data.ebr[batch.batch_id] : undefined;
  const operativo = data.mode === "live" && session && roleRank(session.role) >= 1;

  const descargarPdf = async () => {
    if (!batch || data.mode !== "live") return;
    try {
      const r = await fetch(`${cfg.dlUrl}/api/v1/batches/${batch.batch_id}/ebr/pdf`,
                            { headers: { Authorization: `Bearer ${cfg.token}` } });
      if (!r.ok) throw new Error(String(r.status));
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `ebr_${batch.batch_id}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(`No se pudo descargar: ${(e as Error).message}`);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Lote:</span>
        <Select value={batch?.batch_id} onValueChange={onSelect}>
          <SelectTrigger className="w-72 border-slate-700 bg-[#0d1420] font-mono text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="border-slate-700 bg-[#0d1420]">
            {data.batches.map((x) => (
              <SelectItem key={x.batch_id} value={x.batch_id} className="font-mono text-xs">
                {x.batch_id} · {x.product_nuclide}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="flex-1" />
        {batch && doc && data.mode === "live" && (
          <SignDialog cfg={cfg} session={session} batchId={batch.batch_id}
                      disabled={!operativo || batch.status === "voided"}
                      onDone={onChanged} />
        )}
        {data.mode === "live" && doc && (
          <Button variant="outline" size="sm" onClick={() => void descargarPdf()}
                  className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800">
            <Download className="mr-1 h-3.5 w-3.5" /> eBR en PDF
          </Button>
        )}
      </div>

      {!doc ? (
        <Card className="border-slate-800 bg-[#0d1420]">
          <CardContent className="py-10 text-center text-slate-500">
            Este lote aún no tiene eBR consolidado (o el modo demostración solo incluye algunos lotes).
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border-slate-800 bg-[#0d1420]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm text-slate-300">
                <PenLine className="h-4 w-4 text-cyan-400" /> Firmas electrónicas (21 CFR Part 11)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800">
                    <TableHead>Significado</TableHead><TableHead>Firmante</TableHead>
                    <TableHead>Fecha (UTC)</TableHead><TableHead>Hash</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {doc.signatures.map((s) => (
                    <TableRow key={s.signature_id} className="border-slate-800">
                      <TableCell><Badge variant="outline" className="border-cyan-800 text-cyan-300">
                        {MEANING_ES[s.meaning] ?? s.meaning}</Badge></TableCell>
                      <TableCell>{s.signed_by}</TableCell>
                      <TableCell className="text-xs text-slate-400">{fmtTs(s.signed_at)}</TableCell>
                      <TableCell className="font-mono text-xs text-slate-500">{shortHash(s.signature_hash)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <p className="mt-3 text-xs text-slate-600">
                Re-autenticación del firmante en cada firma; cada una queda vinculada
                al hash del registro vigente — un cambio posterior la invalida de
                forma detectable.
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-[#0d1420]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm text-slate-300">
                <FileCheck2 className="h-4 w-4 text-cyan-400" /> Pista de auditoría
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="relative space-y-4 border-l border-slate-700 pl-5">
                {doc.audit_trail.map((e, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[27px] top-1 h-2.5 w-2.5 rounded-full bg-cyan-500" />
                    <p className="text-sm text-slate-200">{ACCION_ES[e.action] ?? e.action}</p>
                    <p className="text-xs text-slate-500">{fmtTs(e.timestamp)} · {e.actor}</p>
                    {e.detail && <p className="text-xs text-slate-600">{e.detail}</p>}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-[#0d1420] lg:col-span-2">
            <CardContent className="flex flex-wrap items-center gap-4 p-4">
              <span className="text-sm text-slate-400">Integridad del documento:</span>
              <Badge variant="outline" className="border-slate-700">{doc.integrity.algorithm.toUpperCase()}</Badge>
              <span className="font-mono text-xs text-slate-500">{doc.integrity.document_hash}</span>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ firmar --- */
function SignDialog({ cfg, session, batchId, disabled, onDone }:
  { cfg: ConsoleConfig; session: Session | null; batchId: string; disabled: boolean; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [meaning, setMeaning] = useState("performed_by");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const rolInsuficiente = session ? roleRank(session.role) < MIN_ROLE[meaning] : true;

  const submit = async () => {
    if (!session) return;
    setBusy(true);
    try {
      await signEbr(cfg, cfg.token, batchId, session.username, password, meaning);
      toast.success(`Firma registrada: ${MEANING_ES[meaning]}`);
      setOpen(false);
      setPassword("");
      onDone();
    } catch (e) {
      toast.error(`Firma rechazada: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={disabled}
                title={disabled ? "Requiere modo en vivo + sesión" : ""}
                className="bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-40">
          <PenLine className="mr-1 h-3.5 w-3.5" /> Firmar eBR
        </Button>
      </DialogTrigger>
      <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
        <DialogHeader><DialogTitle>Firmar electrónicamente</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Significado de la firma</Label>
            <Select value={meaning} onValueChange={setMeaning}>
              <SelectTrigger className="border-slate-700 bg-slate-900"><SelectValue /></SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                <SelectItem value="performed_by">Realizado por (operador+)</SelectItem>
                <SelectItem value="reviewed_by">Revisado por (supervisor+)</SelectItem>
                <SelectItem value="approved_by">Aprobado por (calidad+)</SelectItem>
              </SelectContent>
            </Select>
            {rolInsuficiente && (
              <p className="mt-1 text-xs text-amber-400">
                Tu rol ({session?.role}) no es suficiente para este significado.
              </p>
            )}
          </div>
          <div>
            <Label>Re-autenticación: contraseña de {session?.username}</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   className="border-slate-700 bg-slate-900" />
          </div>
          <p className="text-xs text-slate-500">
            21 CFR §11.200: la firma exige re-autenticación y queda vinculada al
            hash del registro vigente.
          </p>
          <Button onClick={() => void submit()} disabled={busy || rolInsuficiente || !password}
                  className="w-full bg-cyan-600 hover:bg-cyan-500">
            {busy ? "Firmando…" : "Firmar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
