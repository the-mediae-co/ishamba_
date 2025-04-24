import { Injectable } from '@angular/core';
import { User } from '../user';
import { CallCenterData } from '../call-center';

@Injectable({
  providedIn: 'root'
})
export class EnvironmentService {
  user?: User;
  call_center_data?: CallCenterData;
  constructor(user?: User, call_center_data?: CallCenterData) {
    this.user = user;
    this.call_center_data = call_center_data;
   }
}
