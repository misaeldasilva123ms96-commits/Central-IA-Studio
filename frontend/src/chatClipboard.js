// Keep selection copying free of action buttons/SVG, with real code newlines.
function plain(node){
  if(node.nodeType===Node.TEXT_NODE)return node.textContent;
  if(node.nodeType!==Node.ELEMENT_NODE)return '';
  if(node.tagName==='BR')return '\n';
  if(node.tagName==='PRE'){
    const code=node.querySelector('code')||node;
    const text=code.textContent.replace(/\n$/,'');
    const language=code.className?.match(/language-([\w+-]+)/)?.[1]||'';
    const runs=text.match(/`+/g)||[];
    const fence='`'.repeat(Math.max(3,...runs.map(r=>r.length+1)));
    return `\n${fence}${language}\n${text}\n${fence}\n\n`;
  }
  const text=Array.from(node.childNodes).map(plain).join('');
  if(node.tagName==='LI')return '- '+text.trim()+'\n';
  if(['P','DIV','ARTICLE','FOOTER','SUMMARY','H1','H2','H3','H4','UL','OL'].includes(node.tagName))return text+'\n\n';
  return text;
}
export function copyChatSelection(event,root){
  const selection=window.getSelection();
  if(!event.clipboardData||!root||!selection||selection.isCollapsed||selection.rangeCount!==1)return;
  const range=selection.getRangeAt(0);
  if(!root.contains(range.startContainer)||!root.contains(range.endContainer))return;
  const container=document.createElement('div');
  container.append(range.cloneContents());
  container.querySelectorAll('svg,button,[data-copy-exclude],script,iframe,object,[hidden],details:not([open]) > :not(summary)').forEach(n=>n.remove());
  event.clipboardData.setData('text/plain',Array.from(container.childNodes).map(plain).join(''));
  event.clipboardData.setData('text/html',container.innerHTML);
  event.preventDefault();
}
