import { Component } from '@angular/core';
import { EnvironmentService } from '../services/environment.service';
import { CallCenter } from '../call-center';
import { BaseAPIService } from '../services/base-api.service';

@Component({
  selector: 'app-call-centers',
  templateUrl: './call-centers.component.html',
  styleUrls: ['./call-centers.component.css']
})
export class CallCentersComponent {
  current_call_center?: CallCenter;
  call_centers: CallCenter[];
  constructor(public env: EnvironmentService, private api: BaseAPIService) {
    this.current_call_center = env.call_center_data?.current_call_center;
    this.call_centers = env.call_center_data?.call_centers || [];
  }
  changeCurrentCallCenter(call_center_id: string) {
    this.api.post(`/api/callcenters/${call_center_id}/set_current/`, {}).subscribe(
      response => window.location.reload()
    )
  }
}
