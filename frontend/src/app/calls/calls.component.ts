import { Component } from '@angular/core';

@Component({
  selector: 'app-calls',
  templateUrl: './calls.component.html',
  styleUrls: ['./calls.component.css']
})
export class CallsComponent {
  openTab: number = 1
  toggleTabs($tabNumber: number){
    this.openTab = $tabNumber;
  }
}
