import {Injectable} from '@angular/core';
import {HttpClient, HttpErrorResponse, HttpEvent, HttpHeaders, HttpRequest} from '@angular/common/http';
import {Observable, throwError} from 'rxjs';
import {catchError} from 'rxjs/operators';
import { CookieService } from 'ngx-cookie-service';

@Injectable({
    providedIn: 'root'
})
export class BaseAPIService {
    private acceptHeaders = new HttpHeaders({Accept: 'application/json'});
    constructor(private http: HttpClient, private cookieService: CookieService) {}

    private static handleError(error: HttpErrorResponse): Observable<any> {
        /**
         * Handle Error arising from the http request made.
         */
        const msg = (error.message) ? error.message : error.status ? `${error.statusText}` : 'Server error';
        return throwError(msg);
    }

    public list<T>(uri: string, queryParams: {} = {}, fullResponse: boolean = false): Observable<T> {
        /**
         * Get all objects of type T from a provided uri endpoint.
         * @uri: api endpoint.
         * @return: Observable for consumers to subscribe to.
         */
        let options = {headers: this.acceptHeaders, params: queryParams};
        if (fullResponse){
            Object.assign(options, {observe: 'response'});
        }
        return this.http.get<T>( `${uri}`, options).pipe(catchError(BaseAPIService.handleError));
    }

    public listResponse<T>(uri: string, queryParams: {} = {}): Observable<T> {
        return this.http.get<any>(`${uri}`,
            {headers: this.acceptHeaders, params: queryParams, observe: 'response'}
        ).pipe(
            catchError(BaseAPIService.handleError)
        );
    }

    public listWithProgress<T>(uri: string): Observable<HttpEvent<{}>> {
        const request = new HttpRequest(
            'GET', `${uri}`, {},
            {reportProgress: true, headers: this.acceptHeaders});
        return this.http.request(request);
    }

    public retrieve<T>(uri: string, id: string, queryParams: {} = {}): Observable<T> {
        /**
         * Get an object from database.
         * @uri: api endpoint.
         * @id: database id of item.
         * @return Observable for consumers to subscribe to.
         */
        return this.http.get<T>(`${uri}${id}/`,
            {headers: this.acceptHeaders, params: queryParams}).pipe(catchError(BaseAPIService.handleError));
    }

    public create<T>(uri: string, object: T, queryParams: {} = {}, format = 'application/json'): Observable<T> {
        /**
         * Create a Generic object T.
         * @return Observable for consumers to subscribe to.
         */
        return this.http.post<T>(`${uri}`, object,
            {headers: new HttpHeaders({'Content-Type': `${format}`, "X-CSRFToken": this.cookieService.get("csrftoken")}), params: queryParams})
            // .pipe(catchError(BaseAPIService.handleError));
    }

    public post<T>(uri: string, object: T, queryParams: {} = {}, format = 'application/json'): Observable<T> {
        /**
         * Same as create
         */
        return this.create(uri, object, {} = {},  'application/json');
    }

    public postWithProgress<T>(uri: string, data?: any): Observable<HttpEvent<{}>> {
        const request = new HttpRequest(
            'POST', `${uri}`, data,
            {reportProgress: true, headers: this.acceptHeaders});
        return this.http.request(request);
    }

    public put<T>(uri: string, id: string, newObject: T, queryParams: {} = {}, format = 'application/json'): Observable<T> {
        /**
         * Update a database object.
         * @uri: api endpoint for the collections.
         * @id: database id of item to be updated.
         * @new_object: the new object instance.
         * @return Observable for consumers to subscribe to.
         */
        return this.http.put<any>(`${uri}${id}/`, newObject,
            {headers: new HttpHeaders({'Content-Type': `${format}`, "X-CSRFToken": this.cookieService.get("csrftoken")}), params: queryParams})
            .pipe(catchError(BaseAPIService.handleError));
    }

    public patch<T>(uri: string, id: string, updateParams: T, queryParams: {} = {}, format = 'application/json'): Observable<T> {
        /**
         * Partially update a database object.
         * @uri: api endpoint for the collections.
         * @id: database id of item to be updated.
         * @new_object: the new object instance.
         * @return Observable for consumers to subscribe to.
         */
        return this.http.patch<any>(
            `${uri}${id}/`, updateParams,
            {headers: new HttpHeaders({'Content-Type': `${format}`, "X-CSRFToken": this.cookieService.get("csrftoken")}), params: queryParams}
        ).pipe(
            catchError(BaseAPIService.handleError)
        );
    }

    public delete<T>(uri: string, id: string, queryParams: {} = {}): Observable<T> {
        /**
         * Remove object from database.
         * @uri: api endpoint.
         * @id: db ID of object to delete.
         */
        return this.http.delete<T>(`${uri}${id}/`,
            {headers: new HttpHeaders({'Content-Type': 'application/json'}), params: queryParams}).pipe(
            catchError(BaseAPIService.handleError)
        );
    }

    public jsonp<T>(uri: string, callback: string): Observable<T> {
        /**
         * Get all objects of type T from a provided uri endpoint.
         * @uri: api endpoint.
         * @return: Observable for consumers to subscribe to.
         */
        return this.http.jsonp<T>(
            `${uri}`, callback
        ).pipe(catchError(BaseAPIService.handleError));
    }

    public uploadFormData<T>(uri: string, formData: FormData, method: 'post'|'put'|'patch' = 'post'): any {
        const url = `${uri}`;
        if (method === 'post') {
            return this.http.post(url, formData).pipe(catchError(BaseAPIService.handleError));
        } else if (method === 'put') {
            return this.http.put(url, formData).pipe(catchError(BaseAPIService.handleError));
        } else {
            return this.http.patch(url, formData).pipe(catchError(BaseAPIService.handleError));
        }
    }
}
