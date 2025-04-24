import { Component } from '@angular/core';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent {
  showModal: boolean = false;
  toggleModal(){
    this.showModal = !this.showModal;
  }
}
