import http from 'k6/http';
import { check, sleep } from 'k6';
export const options={vus:20,duration:'30s',thresholds:{http_req_failed:['rate<0.01'],http_req_duration:['p(95)<500']}};
export default function(){
  const base=__ENV.COMMOS_URL||'http://localhost:8000';
  const r=http.get(base+'/health');
  check(r,{'health 200':x=>x.status===200});
  sleep(0.2);
}
