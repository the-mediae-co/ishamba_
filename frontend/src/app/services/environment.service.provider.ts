import {EnvironmentService} from './environment.service';

export const EnvironmentServiceFactory = () => {
    // Read environment variables from browser window
    const browserWindow: any = window || {};
    const env = new EnvironmentService(browserWindow['user'], browserWindow['call_center_data']);
    // @ts-ignore
    const browserWindowEnv = browserWindow['__env'] || {};

    for (const key in browserWindowEnv) {
        if (browserWindowEnv.hasOwnProperty(key)) {
            // @ts-ignore
            env[key] = window['__env'][key];
            // env[key] = deepmerge.all([env[key], window['__env'][key]]);
        }
    }
    return env;
};

export const EnvironmentServiceProvider = {
    provide: EnvironmentService,
    useFactory: EnvironmentServiceFactory,
    deps: [],
};
