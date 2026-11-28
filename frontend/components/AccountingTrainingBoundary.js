'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {usePathname} from 'next/navigation';
import {AccountingTrainingCoach} from './AccountingTrainingCoach';

export default function AccountingTrainingBoundary() {
  const pathname=usePathname();
  const [message,setMessage]=useState('');
  const enabled=process.env.NEXT_PUBLIC_ACCOUNTING_TRAINING==='1';
  useEffect(()=>{
    if(!enabled)return;
    function protect(event){
      const link=event.target?.closest?.('a');
      if(!link?.href)return;
      const target=new URL(link.href,window.location.href);
      if(target.origin!==window.location.origin&&!['blob:'].includes(target.protocol)){
        event.preventDefault();event.stopPropagation();
        setMessage('Connected live applications are outside this fictional practice. Return to your course for the next task.');
      }
    }
    document.addEventListener('click',protect,true);
    return()=>document.removeEventListener('click',protect,true);
  },[enabled]);
  if(!enabled)return null;
  return <>{message&&<div role="alert" className="accounting-training-network-notice"><p>{message}</p><button onClick={()=>setMessage('')}>Dismiss</button><Link href="/training">Return to training</Link></div>}{!pathname.startsWith('/training')&&<AccountingTrainingCoach/>}</>;
}
