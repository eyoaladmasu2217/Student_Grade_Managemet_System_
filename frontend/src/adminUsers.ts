import { apiRequest, User } from "./api";

const pageSize = 200;

export async function loadAllUsers(
  request: (path: string) => Promise<User[]> = apiRequest,
): Promise<User[]> {
  const users: User[] = [];
  let offset = 0;

  while (true) {
    const page = await request(`/api/users?limit=${pageSize}&offset=${offset}`);
    users.push(...page);
    if (page.length < pageSize) return users;
    offset += page.length;
  }
}
