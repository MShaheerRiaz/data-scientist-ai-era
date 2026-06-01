import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class FacebookGraphApiCredentials implements ICredentialType {
	name = 'facebookGraphApiCredentials';
	displayName = 'Facebook Graph API';
	documentationUrl = 'https://developers.facebook.com/docs/pages/access-tokens';
	properties: INodeProperties[] = [
		{
			displayName: 'Page Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'Long-lived Page Access Token from Meta Business Suite → Settings → Page Access Tokens',
		},
		{
			displayName: 'API Version',
			name: 'apiVersion',
			type: 'string',
			default: 'v21.0',
			hint: 'Facebook Graph API version (e.g. v21.0)',
		},
	];
	test = {
		request: {
			baseURL: '=https://graph.facebook.com/{{$credentials.apiVersion}}',
			url: '/me',
			qs: {
				access_token: '={{$credentials.accessToken}}',
			},
		},
	};
}
