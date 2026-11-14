export function chartViewport(width,height,xZoom) {
  return {width,height,plotWidth:Math.max(1,width-120),bottom:Math.max(31,height-(xZoom?65:45))}
}
