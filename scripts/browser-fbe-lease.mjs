import net from 'node:net';

/** An OS-owned loopback lease survives the Python parent and dies with Node. */
export async function acquireBrowserLease(port=8932){
 const server=net.createServer(socket=>socket.destroy());
 await new Promise((resolve,reject)=>{
  server.once('error',reject);
  server.listen(port,'127.0.0.1',resolve);
 });
 return server;
}
