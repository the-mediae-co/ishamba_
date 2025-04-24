import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { MessagesComponent } from './messages/messages.component';
import { CustomersComponent } from './customers/customers.component';
import { HomeComponent } from './home/home.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { SettingsComponent } from './settings/settings.component';
import { TasksComponent } from './tasks/tasks.component';
import { CallsComponent } from './calls/calls.component';
import { CommoditiesComponent as CommoditiesComponent } from './commodities/commodities.component';
import { CommodityComponent } from './commodity/commodity.component';
import { MessageRecipientsComponent } from './message-recipients/message-recipients.component';

const routes: Routes = [
  {path: 'home', component: HomeComponent},
  {path: 'customers', component: CustomersComponent},
  {path: 'messages', component: MessagesComponent},
  {path: 'messages/:message_id', component: MessageRecipientsComponent},
  {path: 'calls', component: CallsComponent},
  {path: 'tasks', component: TasksComponent},
  {path: 'commodities', component: CommoditiesComponent},
  {path: 'commodities/:commodity_id', component: CommodityComponent},
  {path: 'dashboard', component: DashboardComponent},
  {path: 'settings', component: SettingsComponent},
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
