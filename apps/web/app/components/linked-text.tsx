import { Fragment } from 'react';

export function LinkedText({ text }: { text: string }) {
  return <>{text.split(/(https:\/\/[^\s<>\[\]]+)/g).map((part, index) => {
    if (!part.startsWith('https://')) return part;
    const href = part.replace(/[.,;!?)]*$/, '');
    try {
      const url = new URL(href);
      if (url.protocol !== 'https:' || url.username || url.password) return part;
    } catch { return part; }
    return <Fragment key={index}><a href={href} target="_blank" rel="noopener noreferrer">{href}</a>{part.slice(href.length)}</Fragment>;
  })}</>;
}
