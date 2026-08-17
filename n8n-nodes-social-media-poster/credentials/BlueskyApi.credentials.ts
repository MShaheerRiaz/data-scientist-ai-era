import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class BlueskyApiCredentials implements ICredentialType {
	name = 'blueskyApiCredentials';
	displayName = 'Bluesky App Password';
	documentationUrl = 'https://atproto.com/specs/handle';
	properties: INodeProperties[] = [
		{
			displayName: 'Handle',
			name: 'identifier',
			type: 'string',
			default: '',
			placeholder: 'your-handle.bsky.social',
			required: true,
		},
		{
			displayName: 'App Password',
			name: 'password',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'Create via Bluesky → Settings → Advanced → App Passwords (NOT your main account password)',
		},
		{
			displayName: 'Service URL',
			name: 'serviceUrl',
			type: 'string',
			default: 'https://bsky.social',
			hint: 'Leave as default unless using a self-hosted PDS',
		},
	];
}
