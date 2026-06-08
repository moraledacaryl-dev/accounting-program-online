'use client';
import { useEffect, useState } from 'react';
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import { createTaxonomyNode, deleteTaxonomyNode, fetchTaxonomyNodes, updateTaxonomyNode } from '../../lib/api';

export default function TaxonomyAdminPage(){
  const confirmAction = useConfirmAction();
  const [rows,setRows] = useState([]);
  const [editingId,setEditingId] = useState(null);
  const [form,setForm] = useState({module_slug:'rooms', module_name:'Rooms', category:'Revenue', bucket:'Direct Bookings', item:'Walk-in', is_active:true});
  async function load(){
    const data = await fetchTaxonomyNodes();
    setRows(Array.isArray(data) ? data : []);
  }
  useEffect(()=>{ load().catch(console.error); },[]);
  async function submit(e){
    e.preventDefault();
    if(editingId) await updateTaxonomyNode(editingId, form); else await createTaxonomyNode(form);
    setEditingId(null); setForm({module_slug:'rooms', module_name:'Rooms', category:'Revenue', bucket:'Direct Bookings', item:'Walk-in', is_active:true}); await load();
  }
  return <div><section className="section"><h1>Taxonomy Admin</h1><p className="muted">Edit categories, subcategories, and level-3 items from the UI.</p></section>
  <div className="grid"><section className="section"><form onSubmit={submit}><div className="form-grid">
    <label>Module Slug<input required value={form.module_slug} onChange={e=>setForm(f=>({...f, module_slug:e.target.value.toLowerCase().replace(/\\s+/g, '-')}))} /></label>
    <label>Module Name<input required value={form.module_name} onChange={e=>setForm(f=>({...f, module_name:e.target.value}))} /></label>
    <label>Category<input required value={form.category} onChange={e=>setForm(f=>({...f, category:e.target.value}))} /></label>
    <label>Bucket<input required value={form.bucket} onChange={e=>setForm(f=>({...f, bucket:e.target.value}))} /></label>
    <label>Item<input required value={form.item} onChange={e=>setForm(f=>({...f, item:e.target.value}))} /></label>
    <label>Status<select value={String(form.is_active)} onChange={e=>setForm(f=>({...f, is_active: e.target.value === 'true'}))}><option value="true">Active</option><option value="false">Inactive</option></select></label>
  </div><button type="submit">{editingId ? 'Update' : 'Add Node'}</button></form></section>
  <section className="section"><table className="table"><thead><tr><th>Module</th><th>Category</th><th>Bucket</th><th>Item</th><th></th></tr></thead><tbody>
    {rows.map(r=><tr key={r.id}><td>{r.module_name}</td><td>{r.category}</td><td>{r.bucket}</td><td>{r.item}</td><td className="row"><button type="button" className="secondary" onClick={()=>{setEditingId(r.id); setForm({module_slug:r.module_slug,module_name:r.module_name,category:r.category,bucket:r.bucket,item:r.item,is_active:r.is_active})}}>Edit</button><button type="button" className="secondary" onClick={async()=>{if (await confirmAction({ title: `Delete taxonomy node ${r.item}?`, description: 'Records that use this taxonomy may become harder to classify in the workspace.' })) {await deleteTaxonomyNode(r.id); await load();}}}>Delete</button></td></tr>)}
  </tbody></table></section></div></div>
}
