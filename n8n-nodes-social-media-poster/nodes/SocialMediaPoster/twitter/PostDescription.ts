import type { INodeProperties } from 'n8n-workflow';

export const twitterFields: INodeProperties[] = [
	{
		displayName: 'Tweet Text',
		name: 'text',
		type: 'string',
		typeOptions: { rows: 4 },
		default: '',
		required: true,
		description: 'Text of the tweet (max 280 characters on free tier)',
		placeholder: 'What\'s happening?',
	},
	{
		displayName: 'Additional Options',
		name: 'additionalOptions',
		type: 'collection',
		placeholder: 'Add Option',
		default: {},
		options: [
			{
				displayName: 'Reply to Tweet ID',
				name: 'replyToTweetId',
				type: 'string',
				default: '',
				description: 'Tweet ID to reply to (leave blank for a new tweet)',
			},
		],
	},
];
