/*

nba_stats.spec.js

Function: To test if the website is able to get NBA player and matchup stats successfully.

Inputs:

None

Output:

None

Time complexity: Not applicable.

Space complexity: Not applicable.

#################################################################################
# Date modified              Modifier             What was modified             #
# 02/12/2026                 Eram Kabir           Finalized V1.0                #
#################################################################################

*/

/*
Libraries
*/

/*
Note: test coverage is not 100% since 2 of the error
codes of the website cannot be tested with Playwright.
This is because the error codes are time-gated,
meaning the tests would fail at certain points of the
year if implemented. As such, these error codes have
been tested manually instead.

In the same vein, the tests for the upcoming games
table have also been omitted, since the data in
that table changes on a daily basis and cannot be
reliably tested with Playwright.
*/

import dotenv from "dotenv";

dotenv.config();

import { test, expect } from "@playwright/test";

test.describe("Nba stats", () => {
    test.beforeEach(async ({ page }) => {
        const timeoutValue = 2000;
        await page.goto(process.env.VITE_FRONTEND_URL);
        const username = process.env.VITE_USERNAME;
        const password = process.env.VITE_PASSWORD;
        await page.locator("text=Login with Google").click();
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(timeoutValue);
        await page.click('[aria-label="Email or phone"]');
        await page.locator('[aria-label="Email or phone"]').pressSequentially(username, { delay: 100 });
        await page.keyboard.press("Enter");
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(timeoutValue);
        await page.click('[aria-label="Enter your password"]');
        await page.locator('[aria-label="Enter your password"]').pressSequentially(password, { delay: 100 });
        await page.keyboard.press("Enter");
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(timeoutValue);
        try {
            const confirmButton = page.locator("text=Not now");
            if (await confirmButton.isVisible({ timeout: 5000 })) {
            await confirmButton.click();
            await page.waitForLoadState("networkidle");
            await page.waitForTimeout(timeoutValue);
            await page.locator('span:has-text("Continue") >> ..').click();
            };
        } catch (e) {};
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(timeoutValue);
        await expect(page.locator("text=Find NBA Projected Stats")).toBeVisible();
    });

    test("user can get player stats", async ({ page }) => {
        const testParamsList = ["Aaron Gordon", "2025-26", "Regular Season", "BKN", '5'];
        const start = 0;
        const numTestParams = 5;
        const allInputs = await page.locator("input").all();
        for (let i=start; i<numTestParams-1; i++){
            await allInputs[i].click();
            await allInputs[i].pressSequentially(testParamsList[i], { delay: 100 });
            const listbox = page.getByRole("listbox");
            await listbox.getByRole("option", { name: testParamsList[i] }).click();
        };
        await allInputs[numTestParams-1].click();
        await allInputs[numTestParams-1].pressSequentially(testParamsList[numTestParams-1], { delay: 100 });
        await page.locator('[type="submit"]').click();
        await page.waitForLoadState("networkidle");
        await expect(page.getByText("Aaron Gordon")).toBeVisible();
    });

    test("user can get matchup stats", async ({ page }) => {
        await page.locator('button:has-text("Switch to Matchup Projections")').click();
        await page.waitForLoadState("networkidle");
        const testParamsList = ["ATL", "2025-26", "Regular Season", "BKN", '5'];
        const start = 0;
        const numTestParams = 5;
        const allInputs = await page.locator("input").all();
        for (let i=start; i<numTestParams-1; i++){
            await allInputs[i].click();
            await allInputs[i].pressSequentially(testParamsList[i], { delay: 100 });
            const listbox = page.getByRole("listbox");
            await listbox.getByRole("option", { name: testParamsList[i] }).click();
        };
        await allInputs[numTestParams-1].click();
        await allInputs[numTestParams-1].pressSequentially(testParamsList[numTestParams-1], { delay: 100 });
        await page.locator('[type="submit"]').click();
        await page.waitForLoadState("networkidle");
        await expect(page.getByRole("heading", { text: "ATL", level: 1 })).toBeVisible();
        await expect(page.getByRole("heading", { text: "BKN", level: 1 })).toBeVisible();
    })

    test("user entered a player and entered their team as the opposing team for player stats", async ({ page }) => {
        const testParamsList = ["Michael Porter Jr.", "2025-26", "Regular Season", "BKN", '5'];
        const start = 0;
        const numTestParams = 5;
        const allInputs = await page.locator("input").all();
        for (let i=start; i<numTestParams-1; i++){
            await allInputs[i].click();
            await allInputs[i].pressSequentially(testParamsList[i], { delay: 100 });
            const listbox = page.getByRole("listbox");
            await listbox.getByRole("option", { name: testParamsList[i] }).click();
        };
        await allInputs[numTestParams-1].click();
        await allInputs[numTestParams-1].pressSequentially(testParamsList[numTestParams-1], { delay: 100 });
        await page.locator('[type="submit"]').click();
        await page.waitForLoadState("networkidle");
        await expect(page.getByText("This player has not played against the entered team. Change either team or leave the field blank for no opposing team projections.")).toBeVisible();
    });

    test("user entered duplicate teams for matchup stats", async ({ page }) => {
        await page.locator('button:has-text("Switch to Matchup Projections")').click();
        await page.waitForLoadState("networkidle");
        const testParamsList = ["BKN", "2025-26", "Regular Season", "BKN", '5'];
        const start = 0;
        const numTestParams = 5;
        const allInputs = await page.locator("input").all();
        for (let i=start; i<numTestParams-1; i++){
            await allInputs[i].click();
            await allInputs[i].pressSequentially(testParamsList[i], { delay: 100 });
            const listbox = page.getByRole("listbox");
            await listbox.getByRole("option", { name: testParamsList[i] }).click();
        };
        await allInputs[numTestParams-1].click();
        await allInputs[numTestParams-1].pressSequentially(testParamsList[numTestParams-1], { delay: 100 });
        await page.locator('[type="submit"]').click();
        await page.waitForLoadState("networkidle");
        await expect(page.getByText("This team has not played against the entered team. Change either team or leave the field blank for no opposing team projections.")).toBeVisible();
    });
});