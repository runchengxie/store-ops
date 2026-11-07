const supported=value=>typeof value==='string'&&/^zh(?:-|$)/i.test(value)?'zh-CN':typeof value==='string'&&/^en(?:-|$)/i.test(value)?'en':null;
/** Explicit sharing link wins; browser language is the first-use default. */
export function resolveStatusLocale(search,saved,languages=[]){
 const linked=supported(new URLSearchParams(search).get('lang'));
 return linked||supported(saved)||languages.map(supported).find(Boolean)||'en';
}
export function withStatusLanguage(href,locale){
 const url=new URL(href);url.searchParams.set('lang',supported(locale)||'en');return url.href;
}
